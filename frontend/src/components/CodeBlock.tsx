import { useState } from "react";
import type { ReactNode } from "react";
import { useT } from "../i18n";
import { copyText } from "../utils/clipboard";

/** Recover the raw source text from a (possibly highlight.js-wrapped) node tree. */
function nodeToText(node: ReactNode): string {
  if (node == null || node === false) return "";
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeToText).join("");
  if (typeof node === "object" && "props" in node) {
    return nodeToText((node as { props: { children?: ReactNode } }).props.children);
  }
  return "";
}

/** A fenced code block: language label and a Copy button over the highlighted `<pre>`. */
export function CodeBlock({ children }: { children?: ReactNode }) {
  const t = useT();
  const [copied, setCopied] = useState(false);

  // react-markdown renders <pre><code class="language-xxx hljs">…</code></pre>.
  // `children` is that single <code> element; read the language off its class
  // and reconstruct the raw source from its (highlighted) descendant text.
  const codeEl = Array.isArray(children) ? children[0] : children;
  const className =
    (codeEl as { props?: { className?: string } })?.props?.className ?? "";
  const match = /language-(\w+)/.exec(className);
  const lang = match?.[1] ?? "text";
  const raw = nodeToText(
    (codeEl as { props?: { children?: ReactNode } })?.props?.children
  );

  const copy = async () => {
    if (await copyText(raw)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  return (
    <div className="codeblock">
      <div className="codeblock-header">
        <span className="codeblock-lang">{lang}</span>
        <button className="codeblock-copy" onClick={copy}>
          {copied ? t("copied") : t("copy")}
        </button>
      </div>
      <pre>{children}</pre>
    </div>
  );
}
