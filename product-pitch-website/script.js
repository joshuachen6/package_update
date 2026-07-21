const steps = Array.from(document.querySelectorAll(".flow-step"));

if (steps.length > 0) {
  let current = 0;
  setInterval(() => {
    steps[current].classList.remove("active");
    current = (current + 1) % steps.length;
    steps[current].classList.add("active");
  }, 1800);
}

document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener("click", (event) => {
    const id = link.getAttribute("href");
    const target = id ? document.querySelector(id) : null;
    if (target) {
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
});

const escapeHtml = (value) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const renderInline = (value) => {
  let text = escapeHtml(value);
  const codeTokens = [];

  text = text.replace(/`([^`]+)`/g, (_, code) => {
    const token = `@@CODE${codeTokens.length}@@`;
    codeTokens.push(`<code>${code}</code>`);
    return token;
  });

  text = text
    .replace(
      /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
      '$2$1</a>',
    )
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<strong>$1</strong>")
    .replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, "<em>$1</em>");

  codeTokens.forEach((code, index) => {
    text = text.replace(`@@CODE${index}@@`, code);
  });
  return text;
};

const isTableDivider = (line) =>
  /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);

const tableCells = (line) =>
  line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());

const renderMarkdown = (markdown) => {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  const html = [];
  let index = 0;
  let listType = null;

  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`);
      listType = null;
    }
  };

  while (index < lines.length) {
    const line = lines[index];

    if (line.startsWith("```")) {
      closeList();
      const language = line.slice(3).trim();
      const code = [];
      index += 1;
      while (
        index < lines.length &&
        !lines[index].startsWith("```")
      ) {
        code.push(lines[index]);
        index += 1;
      }
      const languageAttribute = language
        ? ` data-language="${escapeHtml(language)}"`
        : "";
      html.push(
        `<pre><code${languageAttribute}>` +
          `${escapeHtml(code.join("\n"))}</code></pre>`,
      );
      index += 1;
      continue;
    }

    if (
      line.includes("|") &&
      index + 1 < lines.length &&
      isTableDivider(lines[index + 1])
    ) {
      closeList();
      const headers = tableCells(line);
      index += 2;
      const rows = [];

      while (
        index < lines.length &&
        lines[index].includes("|") &&
        lines[index].trim()
      ) {
        rows.push(tableCells(lines[index]));
        index += 1;
      }

      html.push(
        '<div class="markdown-table-wrap">' +
          "<table><thead><tr>",
      );
      headers.forEach((cell) => {
        html.push(`<th>${renderInline(cell)}</th>`);
      });
      html.push("</tr></thead><tbody>");

      rows.forEach((row) => {
        html.push("<tr>");
        headers.forEach((_, cellIndex) => {
          html.push(
            `<td>${renderInline(row[cellIndex] || "")}</td>`,
          );
        });
        html.push("</tr>");
      });

      html.push("</tbody></table></div>");
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      closeList();
      const level = heading[1].length;
      html.push(
        `<h${level}>${renderInline(heading[2])}</h${level}>`,
      );
      index += 1;
      continue;
    }
    const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
    const ordered = line.match(/^\s*\d+\.\s+(.+)$/);
    if (unordered || ordered) {
      const nextType = unordered ? "ul" : "ol";
      if (listType !== nextType) {
        closeList();
        listType = nextType;
        html.push(`<${listType}>`);
      }
      html.push(
        `<li>${renderInline((unordered || ordered)[1])}</li>`,
      );
      index += 1;
      continue;
    }

    closeList();

    if (/^\s*---+\s*$/.test(line)) {
      html.push("<hr>");
    } else if (line.startsWith("> ")) {
      html.push(
        `<blockquote>${renderInline(line.slice(2))}</blockquote>`,
      );
    } else if (line.trim()) {
      const paragraph = [line.trim()];

      while (
        index + 1 < lines.length &&
        lines[index + 1].trim() &&
        !/^(#{1,4})\s+/.test(lines[index + 1]) &&
        !/^\s*[-*+]\s+/.test(lines[index + 1]) &&
        !/^\s*\d+\.\s+/.test(lines[index + 1]) &&
        !lines[index + 1].startsWith("```") &&
        !lines[index + 1].startsWith("> ") &&
        !(
          lines[index + 1].includes("|") &&
          index + 2 < lines.length &&
          isTableDivider(lines[index + 2])
        )
      ) {
        paragraph.push(lines[index + 1].trim());
        index += 1;
      }

      html.push(
        `<p>${renderInline(paragraph.join(" "))}</p>`,
      );
    }

    index += 1;
  }

  closeList();
  return html.join("");
};
const loadReport = async () => {
  const content = document.querySelector("#report-content");
  const status = document.querySelector("#report-status");
  if (!content || !status) {
    return;
  }

  try {
    const response = await fetch("report.md", {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const markdown = await response.text();
    if (!markdown.trim()) {
      throw new Error("report.md is empty");
    }

    content.innerHTML = renderMarkdown(markdown);
    status.textContent = "Rendered from report.md";
  } catch (error) {
    status.textContent = "Sample report unavailable";
    content.innerHTML = `
      <div class="report-error">
        <strong>Add report.md beside ui.png to display it here.</strong>
        <span>
          The page fetches and renders the file automatically when
          served through a web server.
        </span>
      </div>`;
  }
};

loadReport();
