import Mechanogenesis.Kernel.Quantity
import Mechanogenesis.Kernel.Frame
import Mechanogenesis.Kernel.World
import Mechanogenesis.Kernel.AssumptionLedger
import Mechanogenesis.Kernel.Evidence
import Mechanogenesis.Kernel.RefinementContract
import Mechanogenesis.Kernel.PhysicalTransition
import Mechanogenesis.Kernel.Promotion
import Mechanogenesis.Kernel.FixtureCertificate

/- This root module is the authoritative import surface for physical state,
evidence, refinement and promotion semantics. -/

#print axioms Mechanogenesis.quantity_le_trans
#print axioms Mechanogenesis.checked_run_satisfies_contract
#print axioms Mechanogenesis.valid_transition_has_strict_sequence_advance
#print axioms Mechanogenesis.sovereign_promotion_implies_strict_error_improvement
#print axioms Mechanogenesis.sovereign_checker_sound
#print axioms Mechanogenesis.sovereign_promotion_checker_sound
#print axioms Mechanogenesis.checked_certificate_allows_only_accounted_strict_promotion
