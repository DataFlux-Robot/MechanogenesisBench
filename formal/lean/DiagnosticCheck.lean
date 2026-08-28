import Mechanogenesis.Kernel.DiagnosticEvidence
import Lean.Data.Json.Parser
import Lean.Data.Json.FromToJson

open Lean
open Mechanogenesis

def rejectDiagnostic (message : String) : IO UInt32 := do
  IO.eprintln s!"diagnostic-check: {message}"
  pure 2

def main (arguments : List String) : IO UInt32 := do
  let path ← match arguments with
    | [path] => pure path
    | _ => return ← rejectDiagnostic "usage: diagnosticCheck <certificate.json>"
  let source ← try
    IO.FS.readFile path
  catch error =>
    return ← rejectDiagnostic s!"cannot read certificate: {error}"
  let json ← match Json.parse source with
    | .ok value => pure value
    | .error error => return ← rejectDiagnostic s!"invalid JSON: {error}"
  let certificate ← match fromJson? json with
    | .ok value => pure (value : DiagnosticCertificate)
    | .error error =>
      return ← rejectDiagnostic s!"invalid certificate schema: {error}"
  if checkDiagnosticEvidence certificate then
    IO.println "valid pre-reveal artifact-anchored diagnostic certificate"
    pure 0
  else
    rejectDiagnostic "certificate violates diagnostic evidence protocol"
