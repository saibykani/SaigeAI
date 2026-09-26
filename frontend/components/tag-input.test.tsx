import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";

import { TagInput } from "./tag-input";

function Harness({ initial = [] as string[] }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <TagInput id="t" value={value} onChange={setValue} />
      <output data-testid="value">{JSON.stringify(value)}</output>
    </>
  );
}

const value = () => JSON.parse(screen.getByTestId("value").textContent ?? "[]");

describe("TagInput", () => {
  it("adds tags on Enter and de-duplicates case-insensitively", () => {
    render(<Harness initial={["Java"]} />);
    const input = document.getElementById("t") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "Selenium" } });
    fireEvent.keyDown(input, { key: "Enter" });
    fireEvent.change(input, { target: { value: "java" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(value()).toEqual(["Java", "Selenium"]);
  });

  it("splits comma-separated input", () => {
    render(<Harness />);
    const input = document.getElementById("t") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "JMeter, Postman," } });
    expect(value()).toEqual(["JMeter", "Postman"]);
  });

  it("removes tags via button and Backspace", () => {
    render(<Harness initial={["A", "B", "C"]} />);
    fireEvent.click(screen.getByLabelText("Remove B"));
    expect(value()).toEqual(["A", "C"]);
    fireEvent.keyDown(document.getElementById("t")!, { key: "Backspace" });
    expect(value()).toEqual(["A"]);
  });
});
