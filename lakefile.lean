import Lake
open Lake DSL

package «MechanogenesisBenchFormal»

@[default_target]
lean_lib BenchmarkProtocol where
  srcDir := "formal/lean"
  roots := #[`BenchmarkProtocol, `MechanismIR, `GTheta,
    `Mechanogenesis.Kernel.Quantity,
    `Mechanogenesis.Kernel.Frame,
    `Mechanogenesis.Kernel.World,
    `Mechanogenesis.Kernel.AssumptionLedger,
    `Mechanogenesis.Kernel.Evidence,
    `Mechanogenesis.Kernel.RefinementContract,
    `Mechanogenesis.Kernel.PhysicalTransition,
    `Mechanogenesis.Kernel.Promotion,
    `Mechanogenesis.Kernel.FixtureCertificate,
    `Mechanogenesis.SovereignKernel]

lean_exe sovereignCheck where
  srcDir := "formal/lean"
  root := `SovereignCheck

lean_exe promotionCheck where
  srcDir := "formal/lean"
  root := `PromotionCheck
