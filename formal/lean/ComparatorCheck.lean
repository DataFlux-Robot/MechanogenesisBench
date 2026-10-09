import Mechanogenesis.Kernel.ComparatorRefinement
import Lean.Data.Json.Parser
import Lean.Data.Json.FromToJson

open Lean
open Mechanogenesis

def rejectComparator (message : String) : IO UInt32 := do
  IO.eprintln s!"comparator-check: {message}"
  pure 2

def main (arguments : List String) : IO UInt32 := do
  let path ← match arguments with
    | [path] => pure path
    | _ => return ← rejectComparator "usage: comparatorCheck <certificate.json>"
  let source ← try
    IO.FS.readFile path
  catch error =>
    return ← rejectComparator s!"cannot read certificate: {error}"
  let json ← match Json.parse source with
    | .ok value => pure value
    | .error error => return ← rejectComparator s!"invalid JSON: {error}"
  let certificate ← match fromJson? json with
    | .ok value => pure (value : ComparatorRefinementCertificate)
    | .error error => return ← rejectComparator s!"invalid certificate schema: {error}"
  if checkComparatorRefinement certificate then
    IO.println "valid comparator refinement"
    pure 0
  else
    rejectComparator "certificate violates comparator refinement semantics"
