// R22.3.5.3 (APP_TEST): the role combobox (installed models on open, filter, typed tag, missing
// flag) and the model manager (list, download with progress and Cancel, delete with a confirm,
// blocked with a reason for a used model), by keyboard and with roles a screen reader reads.
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { createApiClient, type Schemas } from "@/api/client";
import { ConfirmProvider } from "@/components/ConfirmDialog";
import { formatSize, ModelCombobox, sameTag } from "./ModelCombobox";
import { ModelManager, useModelPulls } from "./ModelManager";

const INSTALLED: Schemas["InstalledModel"][] = [
  { name: "numind/nuextract3:Q6_K", size: 3_100_000_000, modified_at: null, roles: [] },
  { name: "qwen3.5:4b", size: 3_400_000_000, modified_at: null, roles: ["reasoning", "vision"] },
];

function Combo({ installed = INSTALLED, onDownload = vi.fn() }: { installed?: Schemas["InstalledModel"][]; onDownload?: (t: string) => void }) {
  const [value, setValue] = useState("qwen3.5:4b");
  return (
    <>
      <ModelCombobox role="vision" value={value} onChange={setValue} installed={installed} onDownload={onDownload} />
      <output data-testid="value">{value}</output>
    </>
  );
}

describe("ModelCombobox", () => {
  it("shows every installed model with its size on open, then filters as typed", () => {
    render(<Combo />);
    const box = screen.getByRole("combobox", { name: "Model for vision" });
    expect(box).toHaveAttribute("aria-expanded", "false");
    fireEvent.focus(box);
    expect(box).toHaveAttribute("aria-expanded", "true");
    const list = screen.getByRole("listbox", { name: "Installed models for vision" });
    const options = within(list).getAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual(["numind/nuextract3:Q6_K3.1 GB", "qwen3.5:4b3.4 GB"]);
    fireEvent.change(box, { target: { value: "nuex" } });
    expect(within(list).getAllByRole("option")).toHaveLength(1);
  });

  it("picks by keyboard and accepts a typed tag, flagging one that is not installed", () => {
    const onDownload = vi.fn();
    render(<Combo onDownload={onDownload} />);
    const box = screen.getByRole("combobox", { name: "Model for vision" });
    fireEvent.focus(box);
    fireEvent.keyDown(box, { key: "ArrowDown" });
    expect(box.getAttribute("aria-activedescendant")).toBeTruthy();
    fireEvent.keyDown(box, { key: "Enter" });
    expect(screen.getByTestId("value")).toHaveTextContent("numind/nuextract3:Q6_K");
    expect(screen.queryByTestId("model-missing")).toBeNull();

    fireEvent.change(box, { target: { value: "qwen3.5:9b" } });
    fireEvent.keyDown(box, { key: "Escape" });
    expect(box).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByTestId("value")).toHaveTextContent("qwen3.5:9b");
    const flag = screen.getByTestId("model-missing");
    expect(flag).toHaveTextContent("Not installed");
    expect(box).toHaveAttribute("aria-invalid", "true");
    expect(box.getAttribute("aria-describedby")).toBe(flag.id);
    fireEvent.click(within(flag).getByRole("button", { name: "Download" }));
    expect(onDownload).toHaveBeenCalledWith("qwen3.5:9b");
  });

  it("compares tags as Ollama does and formats sizes", () => {
    expect(sameTag("Llama3", "llama3:latest")).toBe(true);
    expect(sameTag("library/qwen3.5:4b", "qwen3.5:4b")).toBe(true);
    expect(sameTag("qwen3.5:4b", "qwen3.5:9b")).toBe(false);
    expect(formatSize(3_400_000_000)).toBe("3.4 GB");
    expect(formatSize(512_000_000)).toBe("512 MB");
  });
});

// --- the model manager over a fake sidecar --------------------------------------------------------

function sse(events: object[], hold?: Promise<void>): Response {
  const enc = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    async start(ctrl) {
      for (const [i, e] of events.entries()) {
        if (hold && i === 2) await hold;
        ctrl.enqueue(enc.encode(`event: models.pull_progress\ndata: ${JSON.stringify(e)}\n\n`));
      }
      ctrl.close();
    },
  });
  return new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } });
}

function setup(opts: { hold?: boolean; installed?: Schemas["InstalledModel"][] } = {}) {
  const models = (opts.installed ?? INSTALLED).map((m) => ({ ...m }));
  const calls: string[] = [];
  let release: () => void = () => {};
  const hold = opts.hold ? new Promise<void>((r) => (release = r)) : undefined;
  let aborted = false;
  const fetchImpl = async (input: string, init?: RequestInit) => {
    const url = new URL(input);
    const method = (init?.method ?? "GET").toUpperCase();
    calls.push(`${method} ${decodeURIComponent(url.pathname)}`);
    if (method === "GET" && url.pathname === "/models") {
      return new Response(
        JSON.stringify({ models, roles: { vision: "qwen3.5:4b", reasoning: "qwen3.5:4b" }, suggested: ["qwen3.5:4b", "numind/nuextract3:Q6_K"] }),
      );
    }
    if (method === "POST" && url.pathname === "/models/pull") {
      const name = (JSON.parse(String(init?.body)) as { name: string }).name;
      init?.signal?.addEventListener("abort", () => {
        aborted = true;
      });
      const ev = (status: string, completed: number | null = null) => ({ model: name, status, completed, total: completed === null ? null : 100, message: null });
      if (name === "nope:1b") {
        return sse([ev("pulling manifest"), { ...ev("error"), message: "No model with this name. Check the spelling of the tag." }]);
      }
      const res = sse([ev("pulling manifest"), ev("downloading", 40), ev("downloading", 100), ev("success")], hold);
      if (init?.signal) {
        const signal = init.signal;
        const reader = res.body!.getReader();
        const body = new ReadableStream<Uint8Array>({
          async pull(ctrl) {
            const abort = new Promise<never>((_, rej) => signal.addEventListener("abort", () => rej(new DOMException("aborted", "AbortError"))));
            const r = await Promise.race([reader.read(), abort]);
            if (r.done) {
              models.push({ name, size: 1_000_000_000, modified_at: null, roles: [] });
              ctrl.close();
            } else ctrl.enqueue(r.value);
          },
        });
        return new Response(body, { status: 200 });
      }
      return res;
    }
    if (method === "DELETE" && url.pathname.startsWith("/models/")) {
      const name = decodeURIComponent(url.pathname.slice("/models/".length));
      const i = models.findIndex((m) => m.name === name);
      models.splice(i, 1);
      return new Response(null, { status: 204 });
    }
    return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
  };
  const api = createApiClient({ baseUrl: "http://127.0.0.1:9", token: "t" }, fetchImpl);

  function Harness() {
    const [inv, setInv] = useState<Schemas["ModelInventory"] | null>(null);
    const reload = () => void api.get("/models").then(setInv);
    const [first, setFirst] = useState(true);
    if (first) {
      setFirst(false);
      reload();
    }
    const pulls = useModelPulls(api, reload);
    return <ModelManager api={api} inventory={inv} loadError={null} reload={reload} pulls={pulls} />;
  }
  render(
    <ConfirmProvider>
      <Harness />
    </ConfirmProvider>,
  );
  return { calls, release, wasAborted: () => aborted };
}

describe("ModelManager", () => {
  it("lists installed models with size and roles; a used model cannot be deleted and says why", async () => {
    setup();
    const list = await screen.findByRole("list", { name: "Installed models" });
    const used = within(list).getAllByTestId("installed-model")[1]!;
    expect(used).toHaveTextContent("qwen3.5:4b");
    expect(used).toHaveTextContent("3.4 GB");
    const del = within(used).getByRole("button", { name: "Delete qwen3.5:4b" });
    expect(del).toBeDisabled();
    expect(del).toHaveAccessibleDescription(/Used by: student answer reader and grading — pick another model/);
  });

  it("deletes an unused model after the confirm", async () => {
    const { calls } = setup();
    const del = await screen.findByRole("button", { name: "Delete numind/nuextract3:Q6_K" });
    expect(del).toBeEnabled();
    del.focus();
    fireEvent.click(del);
    const dialog = (await screen.findByTestId("confirm-ok")).closest<HTMLElement>("[role]")!;
    expect(dialog).toHaveTextContent("Delete numind/nuextract3:Q6_K?");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete model" }));
    await waitFor(() => expect(calls).toContain("DELETE /models/numind/nuextract3:Q6_K"));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Delete numind/nuextract3:Q6_K" })).toBeNull());
    // WCAG 2.4.3: the next model is in use (its Delete is disabled), so focus goes to the Download field
    await waitFor(() => expect(document.activeElement).toBe(screen.getByLabelText("Download a model")));
  });

  it("after a delete, focus goes to the next model's Delete button", async () => {
    setup({ installed: [INSTALLED[0]!, { name: "tiny:1b", size: 1_000_000_000, modified_at: null, roles: [] }, INSTALLED[1]!] });
    const del = await screen.findByRole("button", { name: "Delete numind/nuextract3:Q6_K" });
    del.focus();
    fireEvent.click(del);
    fireEvent.click(await screen.findByRole("button", { name: "Delete model" }));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("button", { name: "Delete tiny:1b" })));
  });

  it("downloads a typed tag with progress, then lists it", async () => {
    setup();
    await screen.findByRole("list", { name: "Installed models" });
    const field = screen.getByLabelText("Download a model");
    fireEvent.change(field, { target: { value: "tinyllama:1.1b" } });
    fireEvent.submit(field.closest("form")!);
    await waitFor(() => expect(screen.getByTestId("download-row")).toHaveAttribute("data-status", "success"));
    expect(screen.getByTestId("download-status")).toHaveTextContent("Downloaded");
    await screen.findByRole("button", { name: "Delete tinyllama:1.1b" });
  });

  it("Cancel aborts the request and nothing is listed", async () => {
    const { wasAborted } = setup({ hold: true });
    await screen.findByRole("list", { name: "Installed models" });
    fireEvent.change(screen.getByLabelText("Download a model"), { target: { value: "big:70b" } });
    fireEvent.submit(screen.getByLabelText("Download a model").closest("form")!);
    const cancel = await screen.findByRole("button", { name: "Cancel download of big:70b" });
    expect(screen.getByTestId("download-progress")).toBeInTheDocument();
    await act(async () => fireEvent.click(cancel));
    await waitFor(() => expect(screen.getByTestId("download-row")).toHaveAttribute("data-status", "cancelled"));
    expect(wasAborted()).toBe(true);
    expect(screen.getByTestId("download-status")).toHaveTextContent("Cancelled");
    expect(screen.queryByRole("button", { name: "Delete big:70b" })).toBeNull();
  });

  it("shows a download error in plain words", async () => {
    setup();
    await screen.findByRole("list", { name: "Installed models" });
    fireEvent.change(screen.getByLabelText("Download a model"), { target: { value: "nope:1b" } });
    fireEvent.submit(screen.getByLabelText("Download a model").closest("form")!);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No model with this name. Check the spelling of the tag.");
  });
});
