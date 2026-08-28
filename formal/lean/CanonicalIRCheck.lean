import Mechanogenesis.Kernel.CanonicalIR
import Lean.Data.Json.Parser
import Lean.Data.Json.FromToJson

open Lean
open Mechanogenesis

def rejectCanonicalIr (message : String) : IO UInt32 := do
  IO.eprintln s!"canonical-ir-check: {message}"
  pure 2

def main (arguments : List String) : IO UInt32 := do
  let path ← match arguments with
    | [path] => pure path
    | _ => return ← rejectCanonicalIr "usage: canonicalIRCheck <manifest.json>"
  let source ← try
    IO.FS.readFile path
  catch error =>
    return ← rejectCanonicalIr s!"cannot read manifest: {error}"
  let json ← match Json.parse source with
    | .ok value => pure value
    | .error error => return ← rejectCanonicalIr s!"invalid JSON: {error}"
  let manifest ← match fromJson? json with
    | .ok value => pure (value : CanonicalProgramManifest)
    | .error error => return ← rejectCanonicalIr s!"invalid manifest schema: {error}"
  if checkCanonicalProgram manifest then
    IO.println "valid canonical program"
    pure 0
  else
    rejectCanonicalIr "manifest violates canonical IR semantics"
