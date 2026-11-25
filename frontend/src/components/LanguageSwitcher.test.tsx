import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { LanguageProvider } from "../i18n";
import { LanguageSwitcher } from "./LanguageSwitcher";

class CountingSubmit {
  calls = 0;
  onSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    this.calls += 1;
  };
}

beforeEach(() => {
  localStorage.clear();
});

describe("LanguageSwitcher", () => {
  it("choosing a language does not submit the surrounding form", () => {
    const submit = new CountingSubmit();
    render(
      <LanguageProvider>
        <form onSubmit={submit.onSubmit}>
          <LanguageSwitcher />
        </form>
      </LanguageProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "IT" }));

    expect(submit.calls).toBe(0);
    expect(screen.getByRole("button", { name: "IT" }).getAttribute("aria-pressed")).toBe("true");
  });
});
