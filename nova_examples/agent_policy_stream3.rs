use flate2::{write::ZlibEncoder, Compression};
use nova_snark::{
    frontend::{
        gadgets::{
            boolean::Boolean,
            num::AllocatedNum,
        },
        ConstraintSystem,
        SynthesisError,
    },
    nova::{CompressedSNARK, PublicParams, RecursiveSNARK},
    provider::{Bn256EngineKZG, GrumpkinEngine},
    traits::{
        circuit::StepCircuit,
        snark::RelaxedR1CSSNARKTrait,
        Engine,
        Group,
    },
};
use ff::{Field, PrimeField, PrimeFieldBits};
use std::time::Instant;

type E1 = Bn256EngineKZG;
type E2 = GrumpkinEngine;

type EE1 = nova_snark::provider::hyperkzg::EvaluationEngine<E1>;
type EE2 = nova_snark::provider::ipa_pc::EvaluationEngine<E2>;

type S1 = nova_snark::spartan::snark::RelaxedR1CSSNARK<E1, EE1>;
type S2 = nova_snark::spartan::snark::RelaxedR1CSSNARK<E2, EE2>;

use std::fs::File;
use std::io::{BufRead, BufReader};

#[derive(Clone, Debug)]
struct BudgetCircuit<G: Group> {
    amount: G::Scalar,
}

impl<G> StepCircuit<G::Scalar> for BudgetCircuit<G>
where
    G: Group,
    G::Scalar: PrimeField + PrimeFieldBits,
{
    fn arity(&self) -> usize {
        1
    }

    fn synthesize<CS: ConstraintSystem<G::Scalar>>(
        &self,
        cs: &mut CS,
        z: &[AllocatedNum<G::Scalar>],
    ) -> Result<Vec<AllocatedNum<G::Scalar>>, SynthesisError> {

        //
        // Dummy state.
        // Nova requires a state vector, but we do not use it.
        //
        let dummy_state = z[0].clone();

        //
        // Private witness:
        // amount spent in this step
        //
        let amount = AllocatedNum::alloc(
            cs.namespace(|| "amount"),
            || Ok(self.amount),
        )?;

        //
        // Private witness:
        // constraint of +amount spent in one step
        //
        let amount_bits = amount.to_bits_le(
            cs.namespace(|| "amount_bits")
        )?;

        //
        // Enforce:
        //
        // amount < 128
        //
        for (i, bit) in amount_bits.iter().enumerate().skip(7) {
            Boolean::enforce_equal(
                cs.namespace(|| format!("amount_high_bit_{}", i)),
                bit,
                &Boolean::constant(false),
            )?;
        }

        //
        // State does not change.
        //
        Ok(vec![dummy_state])
    }
}

//
// Number of inputs to read
//
const NUM_STEPS: usize = 10;
const FIFO_PATH: &str = "/tmp/agent_pipe";

fn main() {
    println!("Nova Policy Trace Example");
    println!("========================================");

    //
    // Dummy circuit for setup
    //
    let setup_circuit =
        BudgetCircuit::<<E1 as Engine>::GE> {
            amount: <E1 as Engine>::Scalar::ZERO,
        };

    println!("Producing public parameters...");

    let start = Instant::now();

    let pp = PublicParams::<
        E1,
        E2,
        BudgetCircuit<<E1 as Engine>::GE>,
    >::setup(
        &setup_circuit,
        &*S1::ck_floor(),
        &*S2::ck_floor(),
    )
    .unwrap();

    println!("setup took {:?}", start.elapsed());

    let first_circuit =
    BudgetCircuit::<<E1 as Engine>::GE> {
        amount: <E1 as Engine>::Scalar::ZERO,
    };

    //
    // Public dummy state
    //
    let z0 = vec![
        <E1 as Engine>::Scalar::ZERO
    ];

    type C = BudgetCircuit<<E1 as Engine>::GE>;

    println!("Creating RecursiveSNARK...");

    let mut recursive_snark =
        RecursiveSNARK::<E1, E2, C>::new(
            &pp,
            &first_circuit,
            &z0,
        )
        .unwrap();

    let fifo = File::open(FIFO_PATH).unwrap();

    let reader = BufReader::new(fifo);

    let mut loop_iterations = 0;
    
    for line in reader.lines(){

        let line_str = line.unwrap();
        
        if line_str.trim() == "finish" {
            break;
        }

        let amount: u64 =
            line_str
                .trim()
                .parse()
                .unwrap();

        println!("received {}", amount);

        let circuit =
            BudgetCircuit::<<E1 as Engine>::GE> {
                amount: <E1 as Engine>::Scalar::from(amount),
            };

        let start = Instant::now();

        recursive_snark
            .prove_step(
                &pp,
                &circuit,
            )
            .unwrap();

        loop_iterations += 1;

        println!(
            "prove_step took {:?}",
            start.elapsed()
        );
    }

    println!("Verifying RecursiveSNARK...");

    recursive_snark
        .verify(
            &pp,
            loop_iterations,
            &z0,
        )
        .unwrap();

    println!("RecursiveSNARK verified");

    println!("Creating compressed proof...");

    let (pk, vk) =
        CompressedSNARK::<_, _, _, S1, S2>::setup(&pp)
            .unwrap();

    let compressed_snark =
        CompressedSNARK::<_, _, _, S1, S2>::prove(
            &pp,
            &pk,
            &recursive_snark,
        )
        .unwrap();

    println!("Compressed proof created");

    let mut encoder =
        ZlibEncoder::new(
            Vec::new(),
            Compression::default(),
        );

    bincode::serde::encode_into_std_write(
        &compressed_snark,
        &mut encoder,
        bincode::config::legacy(),
    )
    .unwrap();

    let bytes = encoder.finish().unwrap();

    println!(
        "proof size: {} bytes",
        bytes.len()
    );

    compressed_snark
        .verify(
            &vk,
            loop_iterations,
            &z0,
        )
        .unwrap();

    println!("Compressed proof verified");
}