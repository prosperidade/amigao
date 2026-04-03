import { describe, it, expect, beforeEach } from "vitest"
import { useAuthStore } from "./auth"

describe("useAuthStore", () => {
  beforeEach(() => {
    // Reset store to initial state before each test
    useAuthStore.setState({ token: null, user: null })
  })

  it("starts with null token and user", () => {
    const { token, user } = useAuthStore.getState()
    expect(token).toBeNull()
    expect(user).toBeNull()
  })

  it("setAuth stores token and user", () => {
    const mockUser = {
      id: 1,
      email: "admin@amigao.com",
      full_name: "Admin",
      tenant_id: 10,
    }

    useAuthStore.getState().setAuth("jwt-token-123", mockUser)

    const { token, user } = useAuthStore.getState()
    expect(token).toBe("jwt-token-123")
    expect(user).toEqual(mockUser)
  })

  it("logout clears token and user", () => {
    const mockUser = {
      id: 1,
      email: "admin@amigao.com",
      full_name: "Admin",
      tenant_id: 10,
    }

    useAuthStore.getState().setAuth("jwt-token-123", mockUser)
    useAuthStore.getState().logout()

    const { token, user } = useAuthStore.getState()
    expect(token).toBeNull()
    expect(user).toBeNull()
  })
})
