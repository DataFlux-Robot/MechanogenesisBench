import Mechanogenesis.Kernel.World

namespace Mechanogenesis

def isSha256DigestB (value : String) : Bool :=
  value.startsWith "sha256:" &&
  value.length == 71 &&
  (value.toList.drop 7).all (fun character =>
    "0123456789abcdef".toList.contains character)

def IsSha256Digest (value : String) : Prop :=
  isSha256DigestB value = true

end Mechanogenesis
