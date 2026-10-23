/* Read Inventor iProperties in the browser.

An .ipt or .iam is an OLE compound file. Design-tracking fields and exported
parameters live in property-set streams, including streams stored in the mini
FAT. Flat-pattern extents are centimeters. Custom length, width, height, and
thickness values are converted to inches and become the sheet envelope.
*/
(function () {
  const DESIGN_TRACKING = hex("0f3f85324434d1119e930060b03c1ca6");
  const SUMMARY_INFO = hex("e0859ff29f4f6810ab9108002b27b3d9");
  const USER_DEFINED = hex("b8ad299907643e41b3dccb9ad2f564b7");
  const DOCUMENT_SUMMARY = hex("05d5cdd59c2e1b10939708002b2cf9ae");
  const LENGTH = new Set(["length", "len", "oal", "overalllength"]);
  const WIDTH = new Set(["width", "wid", "oaw", "overallwidth"]);
  const HEIGHT = new Set(["height", "hgt", "oah", "overallheight"]);
  const DEPTH = new Set(["depth", "deep", "oad", "overalldepth"]);
  const THICK = new Set(["thickness", "thick", "thk", "stockthickness"]);
  const UNIT = /^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(inch(?:es)?|in|mm|millimeters?|cm|centimeters?|ft|feet|foot|m|meters?|"|')?\s*$/i;

  function hex(text) {
    const out = new Uint8Array(text.length / 2);
    for (let i = 0; i < out.length; i += 1) out[i] = parseInt(text.substr(i * 2, 2), 16);
    return out;
  }

  function same(a, b) {
    if (!a || !b || a.length !== b.length) return false;
    for (let i = 0; i < a.length; i += 1) if (a[i] !== b[i]) return false;
    return true;
  }

  function read(data, filename, kind) {
    const empty = { ok: false, properties: {}, overall: {}, bomRows: [] };
    const bytes = data instanceof Uint8Array ? data : new Uint8Array(data || []);
    if (bytes.length < 512 || bytes[0] !== 0xd0 || bytes[1] !== 0xcf || bytes[2] !== 0x11 || bytes[3] !== 0xe0) return empty;
    let compound;
    try {
      compound = openCompound(bytes);
    } catch (error) {
      return empty;
    }
    const sets = [];
    let ufrx = new Uint8Array();
    compound.streams.forEach((blob, name) => {
      if (name === "UFRxDoc") ufrx = blob;
      if (blob.length < 28 || blob.length > 2000000 || blob[0] !== 0xfe || blob[1] !== 0xff) return;
      parsePropertyStream(blob).forEach((item) => sets.push(item));
    });
    if (!sets.length) return empty;
    const mapped = mapSets(sets);
    return {
      ok: true,
      properties: mapped.properties,
      overall: mapped.overall,
      bomRows: kind === "iam" ? assemblyRows(ufrx, filename || "") : [],
    };
  }

  function openCompound(bytes) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const sectorShift = view.getUint16(0x1e, true);
    const miniShift = view.getUint16(0x20, true);
    const sectorSize = 1 << sectorShift;
    const miniSize = 1 << miniShift;
    const fatCount = view.getUint32(0x2c, true);
    const firstDir = view.getUint32(0x30, true);
    const cutoff = view.getUint32(0x38, true);
    const firstMini = view.getUint32(0x3c, true);
    const miniFatCount = view.getUint32(0x40, true);
    const firstDifat = view.getUint32(0x44, true);
    if (sectorSize < 512 || sectorSize > 4096) throw new Error("sector");

    function sectorOffset(index) {
      return (index + 1) * sectorSize;
    }

    const fatSectors = [];
    for (let i = 0; i < 109; i += 1) {
      const sec = view.getUint32(0x4c + i * 4, true);
      if (sec <= 0xfffffffa) fatSectors.push(sec);
    }
    let difat = firstDifat;
    let guard = 0;
    while (difat <= 0xfffffffa && guard < 1000) {
      guard += 1;
      const off = sectorOffset(difat);
      const per = sectorSize / 4 - 1;
      for (let i = 0; i < per; i += 1) {
        const sec = view.getUint32(off + i * 4, true);
        if (sec <= 0xfffffffa) fatSectors.push(sec);
      }
      difat = view.getUint32(off + per * 4, true);
    }
    if (fatCount && fatSectors.length > fatCount) fatSectors.length = fatCount;
    const fat = [];
    fatSectors.forEach((sec) => {
      const off = sectorOffset(sec);
      for (let i = 0; i < sectorSize / 4; i += 1) fat.push(view.getUint32(off + i * 4, true));
    });

    function readRegular(start, size) {
      const out = new Uint8Array(size);
      let sec = start;
      let written = 0;
      let hops = 0;
      while (sec <= 0xfffffffa && written < size && hops < 100000) {
        hops += 1;
        const off = sectorOffset(sec);
        const chunk = Math.min(sectorSize, size - written);
        out.set(bytes.subarray(off, off + chunk), written);
        written += chunk;
        sec = fat[sec];
      }
      return out;
    }

    function readChain(start) {
      const chunks = [];
      let sec = start;
      let hops = 0;
      while (sec <= 0xfffffffa && hops < 100000) {
        hops += 1;
        const off = sectorOffset(sec);
        chunks.push(bytes.subarray(off, off + sectorSize));
        sec = fat[sec];
      }
      const out = new Uint8Array(chunks.reduce((sum, chunk) => sum + chunk.length, 0));
      let cursor = 0;
      chunks.forEach((chunk) => {
        out.set(chunk, cursor);
        cursor += chunk.length;
      });
      return out;
    }

    const dirBytes = readChain(firstDir);
    const dirView = new DataView(dirBytes.buffer, dirBytes.byteOffset, dirBytes.byteLength);
    const entries = [];
    for (let pos = 0; pos + 128 <= dirBytes.length; pos += 128) {
      const nameLen = dirView.getUint16(pos + 64, true);
      const type = dirBytes[pos + 66];
      if (!type) continue;
      const chars = Math.max(0, Math.min(nameLen, 64) - 2);
      const name = new TextDecoder("utf-16le").decode(dirBytes.subarray(pos, pos + chars));
      entries.push({
        name,
        type,
        start: dirView.getUint32(pos + 116, true),
        size: dirView.getUint32(pos + 120, true),
      });
    }
    const root = entries.find((entry) => entry.type === 5) || entries[0];
    const miniStream = root ? readRegular(root.start, root.size) : new Uint8Array();
    const miniFatBytes = firstMini <= 0xfffffffa ? readChain(firstMini) : new Uint8Array();
    if (miniFatCount && miniFatBytes.length > miniFatCount * sectorSize) {
      // The chain length is already bounded by the FAT.
    }
    const miniFat = [];
    const miniView = new DataView(miniFatBytes.buffer, miniFatBytes.byteOffset, miniFatBytes.byteLength);
    for (let i = 0; i + 4 <= miniFatBytes.length; i += 4) miniFat.push(miniView.getUint32(i, true));

    function readMini(start, size) {
      const out = new Uint8Array(size);
      let sec = start;
      let written = 0;
      let hops = 0;
      while (sec <= 0xfffffffa && written < size && hops < 100000) {
        hops += 1;
        const off = sec * miniSize;
        const chunk = Math.min(miniSize, size - written);
        out.set(miniStream.subarray(off, off + chunk), written);
        written += chunk;
        sec = miniFat[sec];
      }
      return out;
    }

    const streams = new Map();
    entries.forEach((entry) => {
      if (entry.type !== 2 || !entry.size) return;
      const blob = entry.size < cutoff ? readMini(entry.start, entry.size) : readRegular(entry.start, entry.size);
      streams.set(entry.name, blob);
    });
    return { streams };
  }

  function mapSets(sets) {
    const properties = {};
    const custom = {};
    const tracking = {};
    sets.forEach((item) => {
      if (same(item.fmtid, DESIGN_TRACKING)) Object.assign(tracking, item.props);
      else if (same(item.fmtid, SUMMARY_INFO)) copySummary(properties, item.props);
      else if (same(item.fmtid, USER_DEFINED) || same(item.fmtid, DOCUMENT_SUMMARY)) {
        Object.keys(item.names).forEach((pid) => {
          if (item.props[pid] != null) custom[norm(item.names[pid])] = item.props[pid];
        });
      }
    });
    copyTracking(properties, tracking);
    [
      ["partnumber", "partNumber"],
      ["description", "description"],
      ["material", "material"],
      ["stocknumber", "stockNumber"],
      ["designer", "designer"],
      ["revision", "rev"],
      ["project", "project"],
      ["vendor", "vendor"],
      ["title", "title"],
      ["author", "drawnBy"],
    ].forEach(([key, label]) => {
      if (!properties[label] && custom[key] != null) {
        const text = asText(custom[key]);
        if (text) properties[label] = text;
      }
    });
    let length = named(custom, LENGTH);
    let width = named(custom, WIDTH);
    let height = named(custom, HEIGHT);
    const depth = named(custom, DEPTH);
    const thickness = named(custom, THICK);
    if (length == null) length = fromCm(tracking[64]) || fromCm(tracking[69]);
    if (width == null) width = fromCm(tracking[63]) || fromCm(tracking[68]);
    if (height == null && depth != null) height = depth;
    if (height == null && thickness != null) height = thickness;
    if (width == null && depth != null && height != null && depth !== height) width = depth;
    if (thickness != null) properties.thickness = trim(thickness);
    const overall = length > 0 && width > 0 && height > 0
      ? { length: round(length), width: round(width), height: round(height) }
      : {};
    return { properties, overall };
  }

  function copySummary(props, values) {
    put(props, "title", values[2]);
    put(props, "subject", values[3]);
    put(props, "drawnBy", values[4]);
    put(props, "comments", values[6]);
    put(props, "rev", values[9]);
  }

  function copyTracking(props, values) {
    put(props, "partNumber", values[5]);
    put(props, "project", values[7]);
    put(props, "material", values[20]);
    put(props, "description", values[29]);
    put(props, "vendor", values[30]);
    put(props, "designer", values[41]);
    put(props, "stockNumber", values[55]);
    const density = values[61];
    const mass = values[58];
    const valid = values[62];
    if (valid != null && valid !== 0 && valid !== false && typeof density === "number" && density > 1.5 && typeof mass === "number" && mass > 0) {
      props.mass = trim(mass);
    }
  }

  function put(props, key, value) {
    const text = asText(value);
    if (text && !props[key]) props[key] = text;
  }

  function asText(value) {
    if (value == null || typeof value === "boolean") return "";
    const text = (typeof value === "number" ? trim(value) : String(value)).trim();
    if (!text || text.length > 240) return "";
    if (/[{}<>]/.test(text)) return "";
    const lowered = text.toLowerCase();
    if (lowered.includes("internalname") || lowered.includes("mnemonic=") || text.includes("\\") || text.startsWith("*")) return "";
    return text;
  }

  function named(custom, names) {
    let found = null;
    names.forEach((name) => {
      if (found == null && custom[name] != null) {
        const parsed = inchesFrom(custom[name]);
        if (parsed > 0) found = parsed;
      }
    });
    return found;
  }

  function inchesFrom(value, unitless) {
    let number;
    let unit = unitless || "in";
    if (typeof value === "number") number = value;
    else {
      const match = UNIT.exec(String(value).trim().replace(/,/g, ""));
      if (!match) return null;
      number = Number(match[1]);
      unit = (match[2] || unit).toLowerCase();
    }
    if (unit === "in" || unit === "inch" || unit === "inches" || unit === '"') return number;
    if (unit === "mm" || unit === "millimeter" || unit === "millimeters") return number / 25.4;
    if (unit === "cm" || unit === "centimeter" || unit === "centimeters") return number / 2.54;
    if (unit === "m" || unit === "meter" || unit === "meters") return number * 39.37007874015748;
    if (unit === "ft" || unit === "feet" || unit === "foot" || unit === "'") return number * 12;
    return null;
  }

  function fromCm(value) {
    return typeof value === "number" && value > 0 ? value / 2.54 : null;
  }

  function round(value) {
    return Math.round(value * 1000000) / 1000000;
  }

  function trim(value) {
    return String(round(Number(value)));
  }

  function norm(name) {
    return String(name || "").toLowerCase().replace(/[\s_-]+/g, "");
  }

  function assemblyRows(blob, filename) {
    const own = String(filename).replace(/\.[^.]+$/, "").toLowerCase();
    const counts = {};
    const order = [];
    utf16Strings(blob).forEach((text) => {
      const lowered = text.toLowerCase().replace(/\//g, "\\");
      if (!lowered.includes(".ipt") && !lowered.includes(".iam")) return;
      if (lowered.includes("\\templates\\")) return;
      const pattern = /([^\\/:]+)\.(ipt|iam)\b/ig;
      let match = pattern.exec(text);
      while (match) {
        const stem = match[1].trim();
        const key = stem.toLowerCase();
        if (stem && key !== own && !key.startsWith("standard")) {
          if (counts[key] == null) {
            counts[key] = 0;
            order.push(stem);
          }
          counts[key] += 1;
        }
        match = pattern.exec(text);
      }
    });
    return order.map((stem, index) => ({
      item: String(index + 1),
      partNumber: stem,
      description: "",
      qty: String(counts[stem.toLowerCase()]),
    }));
  }

  function utf16Strings(data) {
    const found = [];
    let index = 0;
    while (index < data.length - 1) {
      let chars = "";
      let cursor = index;
      while (cursor < data.length - 1) {
        const code = data[cursor] | (data[cursor + 1] << 8);
        if (code >= 32 && code <= 126) {
          chars += String.fromCharCode(code);
          cursor += 2;
        } else break;
      }
      if (chars.length >= 3) {
        found.push(chars);
        index = cursor + 2;
      } else index += 1;
    }
    return found;
  }

  function parsePropertyStream(blob) {
    if (blob.length < 48 || blob[0] !== 0xfe || blob[1] !== 0xff) return [];
    const view = new DataView(blob.buffer, blob.byteOffset, blob.byteLength);
    const count = view.getUint32(24, true);
    if (count < 1 || count > 16) return [];
    const found = [];
    for (let index = 0; index < count; index += 1) {
      const base = 28 + index * 20;
      if (base + 20 > blob.length) break;
      const fmtid = blob.subarray(base, base + 16);
      const offset = view.getUint32(base + 16, true);
      const parsed = parseSet(blob, offset);
      if (parsed) found.push({ fmtid, props: parsed.props, names: parsed.names });
    }
    return found;
  }

  function parseSet(blob, offset) {
    const view = new DataView(blob.buffer, blob.byteOffset, blob.byteLength);
    if (offset + 8 > blob.length) return null;
    const count = view.getUint32(offset + 4, true);
    if (count > 10000 || offset + 8 + count * 8 > blob.length) return null;
    const entries = [];
    for (let index = 0; index < count; index += 1) {
      const pos = offset + 8 + index * 8;
      entries.push([view.getUint32(pos, true), view.getUint32(pos + 4, true)]);
    }
    let codepage = 1200;
    entries.forEach(([pid, rel]) => {
      if (pid === 1) {
        const value = variant(blob, offset + rel);
        if (typeof value === "number") codepage = value;
      }
    });
    const props = {};
    let names = {};
    entries.forEach(([pid, rel]) => {
      const absolute = offset + rel;
      if (pid === 0) names = dictionary(blob, absolute, codepage);
      else if (pid !== 1) {
        const value = variant(blob, absolute);
        if (value != null && value !== "") props[pid] = value;
      }
    });
    return { props, names };
  }

  function dictionary(blob, offset, codepage) {
    const view = new DataView(blob.buffer, blob.byteOffset, blob.byteLength);
    if (offset + 4 > blob.length) return {};
    const count = view.getUint32(offset, true);
    if (count > 10000) return {};
    let pos = offset + 4;
    const names = {};
    const unicode = codepage === 1200;
    for (let index = 0; index < count; index += 1) {
      if (pos + 8 > blob.length) break;
      const pid = view.getUint32(pos, true);
      const length = view.getUint32(pos + 4, true);
      pos += 8;
      if (length <= 0 || length > 10000) break;
      let text = "";
      if (unicode) {
        const size = length * 2;
        if (pos + size > blob.length) break;
        text = new TextDecoder("utf-16le").decode(blob.subarray(pos, pos + size)).replace(/\u0000+$/g, "").trim();
        pos += size;
      } else {
        if (pos + length > blob.length) break;
        const raw = blob.subarray(pos, pos + length);
        const zero = raw.indexOf(0);
        text = new TextDecoder("latin1").decode(zero >= 0 ? raw.subarray(0, zero) : raw).trim();
        pos += length;
      }
      if (pos % 4) pos += 4 - (pos % 4);
      if (text) names[pid] = text;
    }
    return names;
  }

  function variant(blob, offset) {
    const view = new DataView(blob.buffer, blob.byteOffset, blob.byteLength);
    if (offset + 4 > blob.length) return null;
    const kind = view.getUint16(offset, true);
    if (kind & 0xf000) return null;
    const data = offset + 4;
    if (kind === 31) {
      if (data + 4 > blob.length) return null;
      const chars = view.getUint32(data, true);
      const size = chars * 2;
      if (chars <= 0 || chars > 100000 || data + 4 + size > blob.length) return null;
      return new TextDecoder("utf-16le").decode(blob.subarray(data + 4, data + 4 + size)).replace(/\u0000+$/g, "").trim();
    }
    if (kind === 30) {
      if (data + 4 > blob.length) return null;
      const size = view.getUint32(data, true);
      if (size <= 0 || size > 100000 || data + 4 + size > blob.length) return null;
      const raw = blob.subarray(data + 4, data + 4 + size);
      const zero = raw.indexOf(0);
      return new TextDecoder("latin1").decode(zero >= 0 ? raw.subarray(0, zero) : raw).trim();
    }
    if (kind === 8) {
      if (data + 4 > blob.length) return null;
      const size = view.getUint32(data, true);
      if (size > 100000 || data + 4 + size > blob.length) return null;
      const raw = blob.subarray(data + 4, data + 4 + size);
      if (size % 2 === 0) {
        const text = new TextDecoder("utf-16le").decode(raw).replace(/\u0000+$/g, "").trim();
        if (text) return text;
      }
      const zero = raw.indexOf(0);
      return new TextDecoder("latin1").decode(zero >= 0 ? raw.subarray(0, zero) : raw).trim();
    }
    if (kind === 2) return data + 2 <= blob.length ? view.getInt16(data, true) : null;
    if (kind === 3 || kind === 22) return data + 4 <= blob.length ? view.getInt32(data, true) : null;
    if (kind === 19) return data + 4 <= blob.length ? view.getUint32(data, true) : null;
    if (kind === 11) return data + 2 <= blob.length ? view.getUint16(data, true) !== 0 : null;
    if (kind === 4) return data + 4 <= blob.length ? view.getFloat32(data, true) : null;
    if (kind === 5) return data + 8 <= blob.length ? view.getFloat64(data, true) : null;
    if (kind === 16) return data < blob.length ? view.getInt8(data) : null;
    if (kind === 17) return data < blob.length ? blob[data] : null;
    return null;
  }

  const SIZE_TOKEN = "(?:\\d+\\s+\\d+/\\d+|\\d+-\\d+/\\d+|\\d+/\\d+|\\d+(?:\\.\\d+)?|\\.\\d+|[¼½¾⅛⅜⅝⅞])";
  const SIZE_TRIPLE = new RegExp(
    `(?:^|[^\\w.])(${SIZE_TOKEN})\\s*(in(?:ch(?:es)?)?|mm|cm|")?\\s*[x×]\\s*(${SIZE_TOKEN})\\s*(in(?:ch(?:es)?)?|mm|cm|")?\\s*[x×]\\s*(${SIZE_TOKEN})\\s*(in(?:ch(?:es)?)?|mm|cm|")?`,
    "i",
  );
  const UNICODE_FRACTIONS = { "¼": 0.25, "½": 0.5, "¾": 0.75, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875 };

  function tokenInches(token, unit) {
    let number;
    if (UNICODE_FRACTIONS[token] != null) number = UNICODE_FRACTIONS[token];
    else {
      const mixed = /^(\d+)[\s-](\d+)\/(\d+)$/.exec(token);
      if (mixed) {
        const denominator = Number(mixed[3]);
        if (!denominator) return null;
        number = Number(mixed[1]) + Number(mixed[2]) / denominator;
      } else if (/^\d+\/\d+$/.test(token)) {
        const parts = token.split("/");
        const denominator = Number(parts[1]);
        if (!denominator) return null;
        number = Number(parts[0]) / denominator;
      } else number = Number(token);
    }
    if (!Number.isFinite(number) || number <= 0) return null;
    return unit ? inchesFrom(`${number} ${unit}`) : inchesFrom(number);
  }

  const SIZE_PAIR = new RegExp(
    `\\((${SIZE_TOKEN})\\s*(in(?:ch(?:es)?)?|mm|cm|")?\\s*[x×]\\s*(${SIZE_TOKEN})\\s*(in(?:ch(?:es)?)?|mm|cm|")?\\)`,
    "i",
  );
  const SIZE_LENGTH = new RegExp(`[-–—]\\s*(${SIZE_TOKEN})\\s*(in(?:ch(?:es)?)?|mm|cm|")?`, "i");

  function sizeFromText(text) {
    const raw = String(text || "");
    const match = SIZE_TRIPLE.exec(raw);
    if (match) {
      const length = tokenInches(match[1], match[2]);
      const width = tokenInches(match[3], match[4]);
      const height = tokenInches(match[5], match[6]);
      if (length > 0 && width > 0 && height > 0) return { length: round(length), width: round(width), height: round(height), plate: true };
    }
    const pair = SIZE_PAIR.exec(raw);
    if (!pair) return null;
    const lengthMatch = SIZE_LENGTH.exec(raw.slice(pair.index + pair[0].length));
    if (!lengthMatch) return null;
    const depth = tokenInches(pair[1], pair[2]);
    const flange = tokenInches(pair[3], pair[4]);
    const length = tokenInches(lengthMatch[1], lengthMatch[2]);
    if (!(depth > 0 && flange > 0 && length > 0)) return null;
    return { length: round(length), width: round(flange), height: round(depth), plate: false };
  }

  const root = typeof globalThis !== "undefined" ? globalThis : window;
  root.drawgenInventor = { read, inchesFrom, sizeFromText };
})();
