import { useEffect } from "react"
import { motion, useSpring, useTransform } from "motion/react"

/** A number that springs to its new value when it changes. */
export function AnimatedNumber({
  value,
  decimals = 0,
  className,
}: {
  value: number
  decimals?: number
  className?: string
}) {
  const spring = useSpring(value, { stiffness: 140, damping: 22, mass: 0.6 })
  const text = useTransform(spring, (v) =>
    v.toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
  )
  useEffect(() => {
    spring.set(value)
  }, [spring, value])
  return <motion.span className={className}>{text}</motion.span>
}
