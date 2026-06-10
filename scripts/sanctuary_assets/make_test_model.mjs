/**
 * Generate the M0 spike asset: a low-poly tree GLB built entirely in code.
 *
 * Why a generated model instead of a downloaded pack model: the spike's job
 * is to verify OUR asset path on device -- gltf-transform output, quantized
 * (KHR_mesh_quantization), textureless flat materials, Metro `.glb` asset
 * loading, GLTFLoader.parse on Hermes. A deterministic generated model makes
 * that reproducible from a clean clone with no network access.
 *
 * Output: mobile/assets/sanctuary/models/dev/spike-tree.glb
 */

import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { Document, NodeIO } from "@gltf-transform/core";
import { KHRMeshQuantization } from "@gltf-transform/extensions";
import { prune, quantize } from "@gltf-transform/functions";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.join(HERE, "..", "..", "mobile", "assets", "sanctuary", "models", "dev");
const OUT_FILE = path.join(OUT_DIR, "spike-tree.glb");

// ---------------------------------------------------------------------------
// Flat-shaded primitive generators. Non-indexed triangles with per-face
// normals so the low-poly facets read crisply under a Lambert material --
// the same look the real pipeline produces.
// ---------------------------------------------------------------------------

/** Push one triangle (flat normal computed from winding). */
function pushTri(pos, nrm, a, b, c) {
  const ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2];
  const vx = c[0] - a[0], vy = c[1] - a[1], vz = c[2] - a[2];
  let nx = uy * vz - uz * vy;
  let ny = uz * vx - ux * vz;
  let nz = ux * vy - uy * vx;
  const len = Math.hypot(nx, ny, nz) || 1;
  nx /= len; ny /= len; nz /= len;
  for (const p of [a, b, c]) {
    pos.push(p[0], p[1], p[2]);
    nrm.push(nx, ny, nz);
  }
}

/** Open cone: tip at y=height, base ring at y=0. Includes base cap. */
function cone(radius, height, segments) {
  const pos = [], nrm = [];
  const tip = [0, height, 0];
  const center = [0, 0, 0];
  for (let i = 0; i < segments; i++) {
    const a0 = (i / segments) * Math.PI * 2;
    const a1 = ((i + 1) / segments) * Math.PI * 2;
    const p0 = [Math.cos(a0) * radius, 0, Math.sin(a0) * radius];
    const p1 = [Math.cos(a1) * radius, 0, Math.sin(a1) * radius];
    pushTri(pos, nrm, p0, tip, p1); // side (outward winding)
    pushTri(pos, nrm, p1, center, p0); // base cap (faces down)
  }
  return { pos: new Float32Array(pos), nrm: new Float32Array(nrm) };
}

/** Closed cylinder from y=0 to y=height. */
function cylinder(radius, height, segments) {
  const pos = [], nrm = [];
  for (let i = 0; i < segments; i++) {
    const a0 = (i / segments) * Math.PI * 2;
    const a1 = ((i + 1) / segments) * Math.PI * 2;
    const b0 = [Math.cos(a0) * radius, 0, Math.sin(a0) * radius];
    const b1 = [Math.cos(a1) * radius, 0, Math.sin(a1) * radius];
    const t0 = [b0[0], height, b0[2]];
    const t1 = [b1[0], height, b1[2]];
    pushTri(pos, nrm, b0, t0, b1);
    pushTri(pos, nrm, b1, t0, t1);
    pushTri(pos, nrm, b1, [0, 0, 0], b0); // bottom cap
    pushTri(pos, nrm, t0, [0, height, 0], t1); // top cap
  }
  return { pos: new Float32Array(pos), nrm: new Float32Array(nrm) };
}

// ---------------------------------------------------------------------------
// Build the document
// ---------------------------------------------------------------------------

function addMesh(doc, buffer, name, geom, material) {
  const position = doc
    .createAccessor(`${name}-pos`)
    .setType("VEC3")
    .setArray(geom.pos)
    .setBuffer(buffer);
  const normal = doc
    .createAccessor(`${name}-nrm`)
    .setType("VEC3")
    .setArray(geom.nrm)
    .setBuffer(buffer);
  const prim = doc
    .createPrimitive()
    .setAttribute("POSITION", position)
    .setAttribute("NORMAL", normal)
    .setMaterial(material);
  return doc.createMesh(name).addPrimitive(prim);
}

async function main() {
  const doc = new Document();
  doc.createExtension(KHRMeshQuantization).setRequired(true);
  const buffer = doc.createBuffer();

  // Palette-style flat colors (sRGB factors, no textures) -- matches the
  // pipeline's "materials sample the 16-slot palette" rule. bark / green_mid.
  const bark = doc
    .createMaterial("bark")
    .setBaseColorFactor([0.42, 0.31, 0.2, 1])
    .setMetallicFactor(0)
    .setRoughnessFactor(1);
  const canopy = doc
    .createMaterial("green_mid")
    .setBaseColorFactor([0.32, 0.55, 0.25, 1])
    .setMetallicFactor(0)
    .setRoughnessFactor(1);

  const trunkMesh = addMesh(doc, buffer, "trunk", cylinder(0.12, 0.6, 7), bark);
  const canopyMesh = addMesh(doc, buffer, "canopy", cone(0.55, 1.3, 8), canopy);

  const trunk = doc.createNode("trunk").setMesh(trunkMesh);
  const canopyNode = doc
    .createNode("canopy")
    .setMesh(canopyMesh)
    .setTranslation([0, 0.55, 0]);

  // Origin at base, unit ~= meters, Y-up: the pipeline's normalization
  // contract. Total height ~1.85.
  const root = doc.createNode("spike-tree").addChild(trunk).addChild(canopyNode);
  doc.createScene("scene").addChild(root);

  await doc.transform(quantize(), prune());

  await mkdir(OUT_DIR, { recursive: true });
  const io = new NodeIO().registerExtensions([KHRMeshQuantization]);
  await io.write(OUT_FILE, doc);

  const tris = (cone(0.55, 1.3, 8).pos.length + cylinder(0.12, 0.6, 7).pos.length) / 9;
  console.log(`wrote ${OUT_FILE} (~${tris} tris, quantized, textureless)`);
}

await main();
