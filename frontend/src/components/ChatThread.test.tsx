import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";
import { ChatThread } from "./ChatThread";
import { LanguageProvider } from "../i18n";
import type { Message } from "../hooks/useConversations";

function assistant(content: string): Message {
  return { id: "m1", role: "assistant", content, created_at: "", attachments: [] };
}

function renderThread(content: string) {
  return render(
    <LanguageProvider>
      <ChatThread
        conversationId="c1"
        messages={[assistant(content)]}
        streamingContent={null}
        streamingThinking={null}
        streamingToolEvents={[]}
        isStreaming={false}
        onEdit={() => {}}
        onRetry={() => {}}
      />
    </LanguageProvider>
  );
}

beforeAll(() => {
  // jsdom has no layout engine; ChatThread auto-scrolls to a bottom ref on mount.
  Element.prototype.scrollIntoView = () => {};
});

describe("ChatThread math rendering", () => {
  it("renders inline $…$ math as KaTeX rather than literal dollar signs", () => {
    const { container } = renderThread("The equation $E = mc^2$ is famous.");

    expect(container.querySelector(".katex")).not.toBeNull();
    expect(container.textContent).not.toContain("$E = mc^2$");
  });

  it("renders a display $$…$$ block", () => {
    const { container } = renderThread("Result:\n\n$$\nE = mc^2\n$$");

    expect(container.querySelector(".katex-display")).not.toBeNull();
  });

  it("leaves dollar signs inside code spans alone", () => {
    renderThread("Run `echo $HOME` first.");

    expect(screen.getByText("echo $HOME")).toBeDefined();
  });

  it("still renders gfm tables alongside math", () => {
    const { container } = renderThread(
      "| a | b |\n| - | - |\n| $x^2$ | 2 |"
    );

    expect(container.querySelector("table")).not.toBeNull();
    expect(container.querySelector("table .katex")).not.toBeNull();
  });
});
