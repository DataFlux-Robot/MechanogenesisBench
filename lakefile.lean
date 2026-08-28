import Lake
open Lake DSL

package «MechanogenesisBenchFormal»

@[default_target]
lean_lib BenchmarkProtocol where
  srcDir := "formal/lean"
  roots := #[`BenchmarkProtocol, `MechanismIR,
    `Mechanogenesis.Kernel.Quantity,
    `Mechanogenesis.Kernel.Frame,
    `Mechanogenesis.Kernel.World,
    `Mechanogenesis.Kernel.Digest,
    `Mechanogenesis.Kernel.AssumptionLedger,
    `Mechanogenesis.Kernel.Evidence,
    `Mechanogenesis.Kernel.RefinementContract,
    `Mechanogenesis.Kernel.PhysicalTransition,
    `Mechanogenesis.Kernel.Promotion,
    `Mechanogenesis.Kernel.FixtureCertificate,
    `Mechanogenesis.Kernel.CanonicalIR,
    `Mechanogenesis.Kernel.MetrologyRefinement,
    `Mechanogenesis.Kernel.ComparatorRefinement,
    `Mechanogenesis.Kernel.RecursiveClosure,
    `Mechanogenesis.Kernel.RecursiveResearchCredit,
    `Mechanogenesis.Kernel.EvidenceActionClosure,
    `Mechanogenesis.Kernel.DiagnosticEvidence,
    `Mechanogenesis.Kernel.IncrementalSeparability,
    `Mechanogenesis.Kernel.Generalization,
    `Mechanogenesis.Kernel.GroundedTestTimeResearch,
    `Mechanogenesis.Kernel.TrajectoryAssets,
    `Mechanogenesis.Kernel.S1CausalContract,
    `Mechanogenesis.Kernel.TraceRefinement,
    `Mechanogenesis.SovereignKernel]

lean_exe sovereignCheck where
  srcDir := "formal/lean"
  root := `SovereignCheck

lean_exe promotionCheck where
  srcDir := "formal/lean"
  root := `PromotionCheck

lean_exe canonicalIRCheck where
  srcDir := "formal/lean"
  root := `CanonicalIRCheck

lean_exe metrologyCheck where
  srcDir := "formal/lean"
  root := `MetrologyCheck

lean_exe comparatorCheck where
  srcDir := "formal/lean"
  root := `ComparatorCheck

lean_exe pipeCheck where
  srcDir := "formal/lean"
  root := `PIPECheck

lean_exe evidenceActionCheck where
  srcDir := "formal/lean"
  root := `EvidenceActionCheck

lean_exe diagnosticCheck where
  srcDir := "formal/lean"
  root := `DiagnosticCheck

lean_exe generalizationCheck where
  srcDir := "formal/lean"
  root := `GeneralizationCheck
