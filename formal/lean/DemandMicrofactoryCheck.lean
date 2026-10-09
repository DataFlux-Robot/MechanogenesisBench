import Mechanogenesis.Kernel.DemandMicrofactory
import Lean.Data.Json.Parser
import Lean.Data.Json.FromToJson

open Lean
open Mechanogenesis

def rejectDemandMicrofactory (message : String) : IO UInt32 := do
  IO.eprintln s!"demand-microfactory-check: {message}"
  pure 2

def main (arguments : List String) : IO UInt32 := do
  let path ← match arguments with
    | [path] => pure path
    | _ => return ← rejectDemandMicrofactory "usage: demandMicrofactoryCheck <certificate.json>"
  let source ← try
    IO.FS.readFile path
  catch error =>
    return ← rejectDemandMicrofactory s!"cannot read certificate: {error}"
  let json ← match Json.parse source with
    | .ok value => pure value
    | .error error =>
      return ← rejectDemandMicrofactory s!"invalid JSON: {error}"
  let certificate ← match fromJson? json with
    | .ok value => pure (value : DemandMicrofactoryCertificate)
    | .error error =>
      return ← rejectDemandMicrofactory s!"invalid certificate schema: {error}"
  if checkDemandMicrofactory certificate then
    IO.println "valid demand, product and three-operator successor certificate"
    pure 0
  else
    rejectDemandMicrofactory "certificate violates microfactory semantics"
