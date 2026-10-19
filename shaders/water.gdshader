shader_type spatial;
render_mode blend_mix, cull_disabled, depth_draw_never, specular_schlick_ggx;

uniform vec4 deep_color : source_color = vec4(0.16, 0.42, 0.42, 1.0);
uniform vec4 shallow_color : source_color = vec4(0.42, 0.72, 0.67, 1.0);
uniform vec4 glow_color : source_color = vec4(0.63, 0.9, 0.84, 1.0);
uniform float flow_speed : hint_range(0.0, 2.0) = 0.45;
uniform float ripple_strength : hint_range(0.0, 1.0) = 0.55;
uniform float ice : hint_range(0.0, 1.0) = 0.0;
uniform float glow : hint_range(0.0, 2.0) = 0.0;
uniform float opacity : hint_range(0.0, 1.0) = 0.84;

varying vec3 world_pos;

float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

void vertex() {
	vec4 wp = MODEL_MATRIX * vec4(VERTEX, 1.0);
	world_pos = wp.xyz;
	// very gentle breathing surface
	VERTEX.y += sin(wp.x * 0.55 + TIME * 0.8) * 0.015 * (1.0 - ice);
}

void fragment() {
	vec2 uv = world_pos.xz * 0.22;
	float t = TIME * flow_speed;
	float wave_a = sin(uv.x * 3.1 + uv.y * 1.7 + t * 1.8);
	float wave_b = sin(uv.x * -2.2 + uv.y * 4.3 - t * 1.25);
	float wave_c = sin((uv.x + uv.y) * 7.1 + t * 2.4);
	float water_normal = (wave_a * 0.5 + wave_b * 0.3 + wave_c * 0.2);

	vec3 n = normalize(vec3(wave_a * 0.08 * ripple_strength, 1.0, wave_b * 0.06 * ripple_strength));
	NORMAL = normalize((VIEW_MATRIX * vec4(n, 0.0)).xyz);

	float fresnel = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 2.6);
	vec3 col = mix(deep_color.rgb, shallow_color.rgb, fresnel * 0.8 + 0.18 + water_normal * 0.08);
	col += glow_color.rgb * smoothstep(0.55, 1.0, wave_c) * 0.12;

	float alpha = mix(opacity, 0.94, fresnel);
	if (ice > 0.001) {
		// frozen branch: milky, fractured surface
		float crack = smoothstep(0.52, 0.58, abs(sin(uv.x * 2.7 + sin(uv.y * 1.9) * 1.6)));
		crack *= smoothstep(0.55, 0.95, sin(uv.y * 5.3 - uv.x * 1.1));
		col = mix(vec3(0.67, 0.82, 0.84), vec3(0.86, 0.94, 0.94), crack * 0.55 + 0.25);
		alpha = mix(alpha, 0.93, ice);
		ROUGHNESS = mix(0.16, 0.48, ice);
		EMISSION = vec3(0.12, 0.25, 0.28) * ice * 0.15;
	} else {
		ROUGHNESS = 0.12;
	}

	if (glow > 0.001) {
		float mote = step(0.986, hash21(floor(world_pos.xz * 1.7)));
		mote *= 0.5 + 0.5 * sin(TIME * 2.0 + world_pos.x * 1.3);
		EMISSION += glow_color.rgb * mote * glow * 0.9;
	}
	ALBEDO = col;
	ALPHA = alpha;
	METALLIC = 0.0;
	SPECULAR = 0.5;
}
