import { describe, it, expect } from "vitest"
import { parseAccessToken, isClientPortalToken } from "./auth"

// Helper to build a fake JWT with a given payload
function fakeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.fake-signature`
}

describe("parseAccessToken", () => {
  it("parses a valid JWT payload", () => {
    const token = fakeJwt({ sub: "42", tenant_id: 1, profile: "internal" })
    const result = parseAccessToken(token)

    expect(result).toEqual({
      sub: "42",
      tenant_id: 1,
      profile: "internal",
    })
  })

  it("returns null for a token with wrong segment count", () => {
    expect(parseAccessToken("only-one-part")).toBeNull()
    expect(parseAccessToken("two.parts")).toBeNull()
  })

  it("returns null for invalid base64 payload", () => {
    expect(parseAccessToken("a.!!!invalid!!!.c")).toBeNull()
  })

  it("returns null for non-JSON payload", () => {
    const header = btoa("header")
    const body = btoa("this is not json")
    expect(parseAccessToken(`${header}.${body}.sig`)).toBeNull()
  })

  it("handles base64url characters (- and _)", () => {
    // Manually create a token with base64url encoding
    const payload = { sub: "user+special/chars" }
    const jsonStr = JSON.stringify(payload)
    const b64 = btoa(jsonStr).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")
    const token = `header.${b64}.sig`

    const result = parseAccessToken(token)
    expect(result).toEqual(payload)
  })
})

describe("isClientPortalToken", () => {
  it("returns true when profile is client_portal", () => {
    const token = fakeJwt({ sub: "1", profile: "client_portal" })
    expect(isClientPortalToken(token)).toBe(true)
  })

  it("returns true when client_id is present", () => {
    const token = fakeJwt({ sub: "1", profile: "internal", client_id: 5 })
    expect(isClientPortalToken(token)).toBe(true)
  })

  it("returns false for internal profile without client_id", () => {
    const token = fakeJwt({ sub: "1", profile: "internal" })
    expect(isClientPortalToken(token)).toBe(false)
  })

  it("returns false for invalid token", () => {
    expect(isClientPortalToken("garbage")).toBe(false)
  })
})
