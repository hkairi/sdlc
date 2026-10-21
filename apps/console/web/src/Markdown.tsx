import type { ReactNode } from "react";

type Props = {
  markdown: string;
};

function inline(text: string): ReactNode[] {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter((part) => part !== "");
  return parts.map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return <span key={index}>{part}</span>;
  });
}

type Block =
  | { kind: "heading"; level: number; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; ordered: boolean; items: string[] }
  | { kind: "quote"; text: string }
  | { kind: "code"; text: string };

function blocks(markdown: string): Block[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const result: Block[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (line.startsWith("```")) {
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith("```")) {
        code.push(lines[index]);
        index += 1;
      }
      index += 1;
      result.push({ kind: "code", text: code.join("\n") });
      continue;
    }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      result.push({ kind: "heading", level: heading[1].length, text: heading[2] });
      index += 1;
      continue;
    }
    if (/^>\s?/.test(line)) {
      result.push({ kind: "quote", text: line.replace(/^>\s?/, "") });
      index += 1;
      continue;
    }
    const list = /^\s*([-*]|\d+\.)\s+(.*)$/.exec(line);
    if (list) {
      const ordered = /\d+\./.test(list[1]);
      const items: string[] = [];
      while (index < lines.length) {
        const match = /^\s*([-*]|\d+\.)\s+(.*)$/.exec(lines[index]);
        if (!match || /\d+\./.test(match[1]) !== ordered) {
          break;
        }
        items.push(match[2]);
        index += 1;
      }
      result.push({ kind: "list", ordered, items });
      continue;
    }
    if (line.trim() === "") {
      index += 1;
      continue;
    }
    const paragraph: string[] = [line];
    index += 1;
    while (index < lines.length && lines[index].trim() !== "" && !/^(#{1,6})\s|^```|^>|^\s*([-*]|\d+\.)\s/.test(lines[index])) {
      paragraph.push(lines[index]);
      index += 1;
    }
    result.push({ kind: "paragraph", text: paragraph.join(" ") });
  }
  return result;
}

export default function Markdown({ markdown }: Props) {
  return (
    <div className="markdown">
      {blocks(markdown).map((block, index) => {
        if (block.kind === "heading") {
          const level = Math.min(6, Math.max(3, block.level + 2));
          const Tag = `h${level}` as "h3" | "h4" | "h5" | "h6";
          return <Tag key={index}>{inline(block.text)}</Tag>;
        }
        if (block.kind === "code") {
          return (
            <pre className="markdown-code" key={index}>
              <code>{block.text}</code>
            </pre>
          );
        }
        if (block.kind === "quote") {
          return <blockquote key={index}>{inline(block.text)}</blockquote>;
        }
        if (block.kind === "list") {
          const List = block.ordered ? "ol" : "ul";
          return (
            <List key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{inline(item)}</li>
              ))}
            </List>
          );
        }
        return <p key={index}>{inline(block.text)}</p>;
      })}
    </div>
  );
}
