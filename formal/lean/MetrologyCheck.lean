import Mechanogenesis.Kernel.MetrologyRefinement
import Lean.Data.Json.Parser
import Lean.Data.Json.FromToJson

open Lean
open Mechanogenesis

def rejectMetrology (message : String) : IO UInt32 := do
  IO.eprintln s!"metrology-check: {message}"
  pure 2

def main (arguments : List String) : IO UInt32 := do
  let path ← match arguments with
    | [path] => pure path
    | _ => return ← rejectMetrology "usage: metrologyCheck <certificate.json>"
  let source ← try
    IO.FS.readFile path
  catch error =>
    return ← rejectMetrology s!"cannot read certificate: {error}"
  let json ← match Json.parse source with
    | .ok value => pure value
    | .error error => return ← rejectMetrology s!"invalid JSON: {error}"
  let certificate ← match fromJson? json with
    | .ok value => pure (value : MetrologyRefinementCertificate)
    | .error error => return ← rejectMetrology s!"invalid certificate schema: {error}"
  if checkMetrologyRefinement certificate then
    IO.println "valid metrology refinement"
    pure 0
  else
    rejectMetrology "certificate violates metrology refinement semantics"
