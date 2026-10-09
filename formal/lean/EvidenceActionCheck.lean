import Mechanogenesis.Kernel.EvidenceActionClosure
import Lean.Data.Json.Parser
import Lean.Data.Json.FromToJson

open Lean
open Mechanogenesis

def rejectEvidenceAction (message : String) : IO UInt32 := do
  IO.eprintln s!"evidence-action-check: {message}"
  pure 2

def main (arguments : List String) : IO UInt32 := do
  let path ← match arguments with
    | [path] => pure path
    | _ => return ← rejectEvidenceAction "usage: evidenceActionCheck <certificate.json>"
  let source ← try
    IO.FS.readFile path
  catch error =>
    return ← rejectEvidenceAction s!"cannot read certificate: {error}"
  let json ← match Json.parse source with
    | .ok value => pure value
    | .error error => return ← rejectEvidenceAction s!"invalid JSON: {error}"
  let certificate ← match fromJson? json with
    | .ok value => pure (value : EvidenceActionCertificate)
    | .error error =>
      return ← rejectEvidenceAction s!"invalid certificate schema: {error}"
  if checkEvidenceActionClosure certificate then
    if certificate.promotionRequested then
      IO.println "valid evidence-action closure; promotion protocol admissible"
    else
      IO.println "valid evidence-action record; promotion safely withheld"
    pure 0
  else
    rejectEvidenceAction "certificate violates evidence-action closure"
