import { describe, it, expect } from "vitest"
import { cn } from "./utils"

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("px-2", "py-1")).toBe("px-2 py-1")
  })

  it("resolves tailwind conflicts (last wins)", () => {
    expect(cn("px-2", "px-4")).toBe("px-4")
  })

  it("handles conditional classes via clsx", () => {
    const showHidden = false
    expect(cn("base", showHidden && "hidden", "extra")).toBe("base extra")
  })

  it("handles undefined and null inputs", () => {
    expect(cn("base", undefined, null, "end")).toBe("base end")
  })

  it("returns empty string for no inputs", () => {
    expect(cn()).toBe("")
  })
})
