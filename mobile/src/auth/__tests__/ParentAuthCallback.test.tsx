import { act, create, type ReactTestRenderer } from "react-test-renderer";

import ParentAuthCallbackScreen from "@/app/auth/callback";

jest.mock("expo-router", () => ({
  Stack: { Screen: () => null },
}));

describe("ParentAuthCallbackScreen", () => {
  it("renders only a generic loading state while MSAL consumes the redirect", async () => {
    let tree!: ReactTestRenderer;
    await act(async () => {
      tree = create(<ParentAuthCallbackScreen />);
    });
    const rendered = JSON.stringify(tree.toJSON());

    expect(rendered).toContain("Finishing secure sign-in");
    expect(rendered).toContain("Keep this tab open");
    expect(rendered).not.toContain("authorization code");
    expect(rendered).not.toContain("state=");
    expect(tree.root.findByProps({ testID: "parent-auth-callback" })).toBeTruthy();

    act(() => tree.unmount());
  });
});
