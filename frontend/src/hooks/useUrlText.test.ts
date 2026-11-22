import { act, renderHook } from "@testing-library/react";

import { useUrlText } from "@/hooks/useUrlText";

it("follows the URL back to a value this field pushed earlier", () => {
  const write = vi.fn();
  const { result, rerender } = renderHook(({ url }) => useUrlText(url, write), {
    initialProps: { url: "" },
  });
  act(() => {
    result.current.choose("kidney");
  });
  rerender({ url: "kidney" });
  rerender({ url: "" }); // Back
  expect(result.current.draft).toBe("");
  rerender({ url: "kidney" }); // Forward
  expect(result.current.draft).toBe("kidney");
});
