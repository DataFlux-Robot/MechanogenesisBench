import Mechanogenesis.SovereignKernel
import Lean.Data.Json.Parser
import Lean.Data.Json.FromToJson

open Lean
open Mechanogenesis

def rejectPromotion (message : String) : IO UInt32 := do
  IO.eprintln s!"promotion-check: {message}"
  pure 2

def main (arguments : List String) : IO UInt32 := do
  let path ← match arguments with
    | [path] => pure path
    | _ => return ← rejectPromotion "usage: promotionCheck <envelope.json>"
  let source ← try
    IO.FS.readFile path
  catch error =>
    return ← rejectPromotion s!"cannot read promotion envelope: {error}"
  let json ← match Json.parse source with
    | .ok value => pure value
    | .error error => return ← rejectPromotion s!"invalid JSON: {error}"
  let envelope ← match fromJson? json with
    | .ok value => pure (value : SovereignPromotionEnvelope)
    | .error error => return ← rejectPromotion s!"invalid envelope schema: {error}"
  if checkSovereignPromotion envelope then
    IO.println "valid sovereign promotion"
    pure 0
  else
    rejectPromotion "promotion violates sovereign kernel semantics"
