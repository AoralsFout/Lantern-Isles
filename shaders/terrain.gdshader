shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform float night_glow : hint_range(0.0, 2.0) = 0.0;
uniform float saturation : hint_range(0.0, 2.0) = 1.0;
uniform float moisture : hint_range(0.0, 1.0) = 0.2;

varying vec3 world_pos;
varying vec3 world_normal;

float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
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

void vertex() {
	vec4 wp = MODEL_MATRIX * vec4(VERTEX, 1.0);
	world_pos = wp.xyz;
	world_normal = normalize(MODEL_NORMAL_MATRIX * NORMAL);
}

void fragment() {
	vec3 col = COLOR.rgb;
	// broad painterly mottling
	float n = vnoise(world_pos.xz * 0.18) * 0.55 + vnoise(world_pos.xz * 0.65) * 0.3;
	col *= 0.9 + n * 0.2;
	// moss / moisture flecks in flat areas
	float flat_mask = smoothstep(0.62, 0.92, world_normal.y);
	float fleck = smoothstep(0.69, 0.98, vnoise(world_pos.xz * 2.6 + 8.0));
	col = mix(col, col * vec3(0.82, 1.02, 0.79), fleck * flat_mask * moisture * 0.35);

	col = mix(vec3(dot(col, vec3(0.299, 0.587, 0.114))), col, 1.08);
	col = pow(col, vec3(1.035));
	ALBEDO = col;
	ROUGHNESS = 0.94;
	SPECULAR = 0.18;

	// tiny bioluminescent pinpricks in the night chapter
	if (night_glow > 0.01) {
		vec2 p = floor(world_pos.xz * 1.9);
		float h = hash21(p);
		vec2 f = fract(world_pos.xz * 1.9) - 0.5;
		float spark = step(0.975, h) * smoothstep(0.13, 0.0, length(f));
		spark *= 0.65 + 0.35 * sin(TIME * 1.7 + h * 20.0);
		EMISSION = vec3(0.38, 0.95, 0.86) * spark * night_glow * 1.8;
	}
}
