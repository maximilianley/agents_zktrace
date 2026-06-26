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
use ff::{PrimeField, PrimeFieldBits};
use std::time::Instant;

type E1 = Bn256EngineKZG;
type E2 = GrumpkinEngine;

type EE1 = nova_snark::provider::hyperkzg::EvaluationEngine<E1>;
type EE2 = nova_snark::provider::ipa_pc::EvaluationEngine<E2>;

type S1 = nova_snark::spartan::snark::RelaxedR1CSSNARK<E1, EE1>;
type S2 = nova_snark::spartan::snark::RelaxedR1CSSNARK<E2, EE2>;

#[derive(Clone, Debug)]
struct BudgetCircuit<G: Group> {
    _marker: std::marker::PhantomData<G>,
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
        let budget = z[0].clone();

        //
        // Convert budget into bits
        //
        let bits = budget.to_bits_le(
            cs.namespace(|| "budget_bits")
        )?;

        //
        // Enforce:
        //
        // budget < 512
        //
        // by forcing all bits above bit 8 to zero.
        //


        /*for (i, bit) in bits.iter().enumerate().skip(9) {
            cs.enforce(
                || format!("high_bit_{}_must_be_zero", i),

                //|lc| lc + bit.get_variable(),
                |lc| lc + bit.lc(CS::one(), G::Scalar::ONE),

                |lc| lc + CS::one(),

                |lc| lc,
            );
        }*/

        for (i, bit) in bits.iter().enumerate().skip(9) {
            Boolean::enforce_equal(
                cs.namespace(|| format!("high_bit_{}_must_be_zero", i)),
                bit,
                &Boolean::constant(false),
            )?;
        }

        //
        // State does not change yet.
        //
        Ok(vec![budget])
    }
}

fn main() {
    println!("Nova Budget Range Example");
    println!("========================================");

    let num_steps = 10;

    let circuit = BudgetCircuit::<<E1 as Engine>::GE> {
        _marker: std::marker::PhantomData,
    };

    println!("Producing public parameters...");

    let start = Instant::now();

    let pp = PublicParams::<
        E1,
        E2,
        BudgetCircuit<<E1 as Engine>::GE>,
    >::setup(
        &circuit,
        &*S1::ck_floor(),
        &*S2::ck_floor(),
    )
    .unwrap();

    println!("setup took {:?}", start.elapsed());

    println!(
        "constraints (primary): {}",
        pp.num_constraints().0
    );

    println!(
        "constraints (secondary): {}",
        pp.num_constraints().1
    );

    //
    // Try values here:
    //
    // 123  -> should succeed
    // 500  -> should succeed
    // 511  -> should succeed
    // 512  -> should fail
    // 700  -> should fail
    //
    let z0 = vec![
        <E1 as Engine>::Scalar::from(423u64)
    ];

    type C = BudgetCircuit<<E1 as Engine>::GE>;

    println!("Creating RecursiveSNARK...");

    let mut recursive_snark =
        RecursiveSNARK::<E1, E2, C>::new(
            &pp,
            &circuit,
            &z0,
        )
        .unwrap();

    for i in 0..num_steps {
        let start = Instant::now();

        recursive_snark
            .prove_step(&pp, &circuit)
            .unwrap();

        println!(
            "prove_step {} took {:?}",
            i,
            start.elapsed()
        );
    }

    println!("Verifying RecursiveSNARK...");

    let start = Instant::now();

    recursive_snark
        .verify(
            &pp,
            num_steps,
            &z0,
        )
        .unwrap();

    println!(
        "verify took {:?}",
        start.elapsed()
    );

    println!("Creating compressed proof...");

    let (pk, vk) =
        CompressedSNARK::<_, _, _, S1, S2>::setup(&pp)
            .unwrap();

    let start = Instant::now();

    let compressed_snark =
        CompressedSNARK::<_, _, _, S1, S2>::prove(
            &pp,
            &pk,
            &recursive_snark,
        )
        .unwrap();

    println!(
        "compressed prove took {:?}",
        start.elapsed()
    );

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
        "compressed proof size: {} bytes",
        bytes.len()
    );

    println!("Verifying compressed proof...");

    let start = Instant::now();

    compressed_snark
        .verify(
            &vk,
            num_steps,
            &z0,
        )
        .unwrap();

    println!(
        "compressed verify took {:?}",
        start.elapsed()
    );
}