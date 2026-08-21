import Lake
open Lake DSL

package «MechanogenesisBenchFormal»

@[default_target]
lean_lib BenchmarkProtocol where
  srcDir := "formal/lean"
  roots := #[`BenchmarkProtocol, `MechanismIR, `GTheta,
    `Mechanogenesis.SovereignKernel]

lean_exe sovereignCheck where
  srcDir := "formal/lean"
  root := `SovereignCheck

lean_exe promotionCheck where
  srcDir := "formal/lean"
  root := `PromotionCheck
