import Mechanogenesis.SovereignKernel
import Lean.Data.Json.Parser
import Lean.Data.Json.FromToJson

open Lean
open Mechanogenesis

def reject (message : String) : IO UInt32 := do
  IO.eprintln s!"sovereign-check: {message}"
  pure 2

def main (arguments : List String) : IO UInt32 := do
  let path ← match arguments with
    | [path] => pure path
    | _ => return ← reject "usage: sovereignCheck <certificate.json>"
  let source ← try
    IO.FS.readFile path
  catch error =>
    return ← reject s!"cannot read certificate: {error}"
  let json ← match Json.parse source with
    | .ok value => pure value
    | .error error => return ← reject s!"invalid JSON: {error}"
  let certificate ← match fromJson? json with
    | .ok value => pure (value : SovereignCertificate)
    | .error error => return ← reject s!"invalid certificate schema: {error}"
  if checkSovereignCertificate certificate then
    IO.println "valid sovereign certificate"
    pure 0
  else
    reject "certificate violates sovereign kernel semantics"
