import { describe, expect, it } from "vitest";
import { interpolate, translate, translations } from "./strings";

describe("interpolate", () => {
  it("fills named placeholders", () => {
    expect(interpolate("Remove {name}", { name: "a.pdf" })).toBe("Remove a.pdf");
  });

  it("leaves unknown placeholders untouched", () => {
    expect(interpolate("Hi {who}", { name: "x" })).toBe("Hi {who}");
  });

  it("returns the template unchanged with no vars", () => {
    expect(interpolate("Send")).toBe("Send");
  });
});

describe("translate", () => {
  it("returns the localized string", () => {
    expect(translate("it", "send")).toBe("Invia");
    expect(translate("de", "send")).toBe("Senden");
  });

  it("falls back to English for a key missing in a language", () => {
    // `appName` is only defined on `en`; it/de inherit it.
    expect(translations.it.appName).toBeUndefined();
    expect(translate("it", "appName")).toBe(translations.en.appName);
  });

  it("interpolates within a localized string", () => {
    expect(translate("de", "removeAttachment", { name: "x.txt" })).toBe(
      "x.txt entfernen"
    );
  });
});
