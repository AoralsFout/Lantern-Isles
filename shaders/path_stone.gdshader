shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;

// A path of worn stone slabs. Voronoi gives the slabs, fbm gives moss, and the
// dirt shoulder blends the ribbon back into the painted terrain.

uniform vec4 stone_a : source_color = vec4(0.48, 0.47, 0.4, 1.0);
uniform vec4 stone_b : source_color = vec4(0.63, 0.59, 0.5, 1.0);
uniform vec4 mortar : source_color = vec4(0.22, 0.24, 0.21, 1.0);
uniform vec4 moss_color : source_color = vec4(0.3, 0.42, 0.27, 1.0);
uniform vec4 edge_dirt : source_color = vec4(0.52, 0.47, 0.36, 1.0);
uniform float slab_scale = 1.15;
uniform float glow : hint_range(0.0, 2.0) = 0.0;

varying vec3 world_pos;
varying float edge_factor;

float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

vec2 hash22(vec2 p) {
	float n = hash21(p);
	return vec2(n, hash21(p + n * 37.0));
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = hash21(i);
	float b = hash21(i + vec2(1.0, 0.0));
	float c = hash21(i + vec2(0.0, 1.0));
	float d = hash21(i + vec2(1.0, 1.0));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
	float v = 0.0;
	float a = 0.5;
	for (int i = 0; i < 4; i++) {
		v += a * vnoise(p);
		p = p * 2.03 + 7.7;
		a *= 0.5;
	}
	return v;
}

// nearest and second-nearest feature point in a jittered grid
vec2 voronoi(vec2 uv, out vec2 cell_id) {
	vec2 n = floor(uv);
	vec2 f = fract(uv);
	float d1 = 8.0;
	float d2 = 8.0;
	cell_id = n;
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 g = vec2(float(x), float(y));
			vec2 o = hash22(n + g);
			vec2 r = g + o - f;
			float d = dot(r, r);
			if (d < d1) {
				d2 = d1;
				d1 = d;
				cell_id = n + g;
			} else if (d < d2) {
				d2 = d;
			}
		}
	}
	return vec2(sqrt(d1), sqrt(d2));
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	edge_factor = abs(UV.x - 0.5) * 2.0;
}

void fragment() {
	vec2 cid;
	vec2 vd = voronoi(world_pos.xz / slab_scale, cid);
	float gap = vd.y - vd.x;
	float mortar_line = 1.0 - smoothstep(0.015, 0.085, gap);
	float tone = hash21(cid);
	vec3 col = mix(stone_a.rgb, stone_b.rgb, tone);
	float grain = fbm(world_pos.xz * 3.1 + 2.0);
	col *= 0.91 + grain * 0.17;
	float moss = smoothstep(0.54, 0.78, fbm(world_pos.xz * 0.55 + 9.0));
	col = mix(col, moss_color.rgb, moss * 0.38);
	col = mix(col, mortar.rgb, mortar_line * 0.5);
	// worn dirt edge
	float edge = smoothstep(0.48, 0.98, edge_factor);
	col = mix(col, edge_dirt.rgb, edge * 0.62);
	// cool / warm micro variation
	col *= 0.96 + 0.08 * smoothstep(0.0, 0.6, fbm(world_pos.xz * 6.0));
	ALBEDO = col;
	ROUGHNESS = 0.95;
	SPECULAR = 0.14;
	if (glow > 0.001) {
		float mote = smoothstep(0.78, 0.95, fbm(world_pos.xz * 1.4 + 4.0));
		EMISSION = mix(moss_color.rgb, vec3(0.55, 0.9, 0.82), 0.5) * mote * glow * 0.5;
	}
}
