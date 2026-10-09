import Mechanogenesis.Kernel.RecursiveClosure
import Lean.Data.Json.Parser
import Lean.Data.Json.FromToJson

open Lean
open Mechanogenesis

def rejectPIPE (message : String) : IO UInt32 := do
  IO.eprintln s!"pipe-check: {message}"
  pure 2

def main (arguments : List String) : IO UInt32 := do
  let path ← match arguments with
    | [path] => pure path
    | _ => return ← rejectPIPE "usage: pipeCheck <witness.json>"
  let source ← try
    IO.FS.readFile path
  catch error =>
    return ← rejectPIPE s!"cannot read PIPE witness: {error}"
  let json ← match Json.parse source with
    | .ok value => pure value
    | .error error => return ← rejectPIPE s!"invalid JSON: {error}"
  let witness ← match fromJson? json with
    | .ok value => pure (value : PIPEWitness)
    | .error error => return ← rejectPIPE s!"invalid PIPE schema: {error}"
  if checkPIPEProtocol witness then
    IO.println "valid PIPE protocol; physical identification remains external"
    pure 0
  else
    rejectPIPE "witness violates PIPE protocol semantics"
