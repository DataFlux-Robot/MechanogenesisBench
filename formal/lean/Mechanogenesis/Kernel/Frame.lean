import Mechanogenesis.Kernel.Quantity

namespace Mechanogenesis

structure FrameId where
  value : String
  deriving DecidableEq, Repr

structure PoseQ where
  frame : FrameId
  translationMicrometres : Int × Int × Int
  rotationMillidegrees : Int × Int × Int
  deriving DecidableEq, Repr

def SameFrame (left right : PoseQ) : Prop :=
  left.frame = right.frame

theorem same_frame_trans
    {first second third : PoseQ}
    (firstSecond : SameFrame first second)
    (secondThird : SameFrame second third) :
    SameFrame first third := by
  exact firstSecond.trans secondThird

end Mechanogenesis
