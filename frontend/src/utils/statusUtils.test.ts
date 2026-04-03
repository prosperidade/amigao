import { describe, it, expect } from "vitest"
import { getStatusStyle } from "./statusUtils"

describe("getStatusStyle", () => {
  describe('comparison = "greater"', () => {
    it('returns "status-ok" when value > threshold', () => {
      expect(getStatusStyle(10, 5, "greater")).toBe("status-ok")
    })

    it('returns "status-alert" when value <= threshold', () => {
      expect(getStatusStyle(5, 5, "greater")).toBe("status-alert")
      expect(getStatusStyle(3, 5, "greater")).toBe("status-alert")
    })
  })

  describe('comparison = "less"', () => {
    it('returns "status-ok" when value < threshold', () => {
      expect(getStatusStyle(3, 5, "less")).toBe("status-ok")
    })

    it('returns "status-alert" when value >= threshold', () => {
      expect(getStatusStyle(5, 5, "less")).toBe("status-alert")
      expect(getStatusStyle(10, 5, "less")).toBe("status-alert")
    })
  })
})
