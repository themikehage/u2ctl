import { describe, expect, test } from "bun:test";
import { formatCompactSnapshot, parseXmlDump } from "../../src/domains/ui";
import { parseSelectorArgs } from "../../src/selectors/parser";
import { resolveSelector } from "../../src/selectors/resolver";
import { renderOutput, formatSuccessEnvelope } from "../../src/output";

describe("u2bun Agent-Browser Parity & Minimal Output", () => {
  const sampleXml = `<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.android.settings" bounds="[0,0][1080,2400]">
    <node index="0" text="Network &amp; internet" resource-id="com.android.settings:id/title" class="android.widget.TextView" package="com.android.settings" bounds="[100,200][500,250]" clickable="true" />
    <node index="1" text="Connected devices" resource-id="com.android.settings:id/title" class="android.widget.TextView" package="com.android.settings" bounds="[100,300][500,350]" clickable="true" />
    <node index="2" text="Search settings" resource-id="com.android.settings:id/search" class="android.widget.EditText" package="com.android.settings" bounds="[50,50][1000,150]" focusable="true" />
  </node>
</hierarchy>`;

  const overlappingXml = `<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.facebook.katana" bounds="[0,0][1080,2400]">
    <node index="1" text="" resource-id="" class="android.widget.Button" package="com.facebook.katana" bounds="[897,430][1044,482]" clickable="true" />
    <node index="2" text="Ver todo" resource-id="" class="android.view.View" package="com.facebook.katana" bounds="[897,430][1044,482]" />
  </node>
</hierarchy>`;

  test("parseXmlDump assigns handles @1, @2, @3 automatically", () => {
    const elements = parseXmlDump(sampleXml);
    expect(elements.length).toBe(3);
    expect(elements[0].ref).toBe("@1");
    expect(elements[1].ref).toBe("@2");
    expect(elements[2].ref).toBe("@3");
  });

  test("formatCompactSnapshot produces ultra-compact LLM text format with semantic roles", () => {
    const elements = parseXmlDump(sampleXml);
    const textSnapshot = formatCompactSnapshot(elements, "com.android.settings", "a1b2c3d4");

    expect(textSnapshot).toContain("[App: com.android.settings | fingerprint: a1b2c3d4]");
    expect(textSnapshot).toContain('[@1] Button "Network & internet"');
    expect(textSnapshot).toContain('[@2] Button "Connected devices"');
    expect(textSnapshot).toContain('[@3] Input "Search settings"');
  });

  test("deduplicates ghost wrappers with overlapping bounds", () => {
    const elements = parseXmlDump(overlappingXml);
    expect(elements.length).toBe(1);
    expect(elements[0].ref).toBe("@1");
    expect(elements[0].text).toBe("Ver todo");
    expect(elements[0].clickable).toBe(true);
  });

  test("parseSelectorArgs parses --ref @1 into query", () => {
    const q1 = parseSelectorArgs({ ref: "@1" });
    expect(q1.ref).toBe("@1");

    const q2 = parseSelectorArgs({ ref: "2" });
    expect(q2.ref).toBe("@2");
  });

  test("resolveSelector matches elements by handle @1", () => {
    const elements = parseXmlDump(sampleXml);
    const query = parseSelectorArgs({ ref: "@2" });
    const match = resolveSelector(elements, query);

    expect(match.element.text).toBe("Connected devices");
    expect(match.centerX).toBe(300);
    expect(match.centerY).toBe(325);
  });

  test("renderOutput renders plain text for snapshot and ok for actions", () => {
    let output = "";
    const originalLog = console.log;
    console.log = (msg: string) => {
      output += msg + "\n";
    };

    try {
      // 1. Action tap -> ok
      output = "";
      renderOutput(formatSuccessEnvelope("ui.tap", "da0f5e72", { tapped: true }), false);
      expect(output.trim()).toBe("ok");

      // 2. Action input -> ok
      output = "";
      renderOutput(formatSuccessEnvelope("ui.input", "da0f5e72", { success: true }), false);
      expect(output.trim()).toBe("ok");

      // 3. Action press -> ok
      output = "";
      renderOutput(formatSuccessEnvelope("ui.press", "da0f5e72", { pressed: true }), false);
      expect(output.trim()).toBe("ok");

      // 4. Snapshot -> plain snapshot string
      output = "";
      renderOutput(formatSuccessEnvelope("ui.snapshot", "da0f5e72", { snapshot: '[App: test]\n[@1] Button "OK"' }), false);
      expect(output.trim()).toBe('[App: test]\n[@1] Button "OK"');
    } finally {
      console.log = originalLog;
    }
  });
});
