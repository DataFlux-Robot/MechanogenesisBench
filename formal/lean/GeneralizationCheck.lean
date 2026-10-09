import Mechanogenesis.Kernel.Generalization
import Lean.Data.Json.Parser
import Lean.Data.Json.FromToJson

open Lean
open Mechanogenesis

def rejectGeneralization (message : String) : IO UInt32 := do
  IO.eprintln s!"generalization-check: {message}"
  pure 2

def main (arguments : List String) : IO UInt32 := do
  let path ← match arguments with
    | [path] => pure path
    | _ => return ← rejectGeneralization "usage: generalizationCheck <certificate.json>"
  let source ← try
    IO.FS.readFile path
  catch error =>
    return ← rejectGeneralization s!"cannot read certificate: {error}"
  let json ← match Json.parse source with
    | .ok value => pure value
    | .error error => return ← rejectGeneralization s!"invalid JSON: {error}"
  let certificate ← match fromJson? json with
    | .ok value => pure (value : GeneralizationCertificate)
    | .error error =>
      return ← rejectGeneralization s!"invalid certificate schema: {error}"
  if certificate.validB then
    if certificate.recursiveClaim then
      IO.println "valid shortcut-destruction, engineering and recursive-value certificate"
    else
      IO.println "valid shortcut-destruction and engineering generalization certificate"
    pure 0
  else
    rejectGeneralization "certificate violates generalization requirements"
