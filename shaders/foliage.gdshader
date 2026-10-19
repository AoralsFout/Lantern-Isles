shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;

uniform vec4 albedo : source_color = vec4(0.6, 0.7, 0.55, 1.0);
uniform float sway : hint_range(0.0, 0.3) = 0.05;
uniform float glow : hint_range(0.0, 4.0) = 0.0;
uniform float roughness : hint_range(0.0, 1.0) = 0.88;

void vertex() {
	vec4 wp = MODEL_MATRIX * vec4(VERTEX, 1.0);
	float phase = wp.x * 0.23 + wp.z * 0.17;
	float k = smoothstep(0.05, 5.0, VERTEX.y);
	VERTEX.x += sin(TIME * 1.15 + phase) * sway * k;
	VERTEX.z += cos(TIME * 0.93 + phase * 1.37) * sway * 0.65 * k;
}

void fragment() {
	ALBEDO = albedo.rgb;
	ROUGHNESS = roughness;
	SPECULAR = 0.25;
	if (glow > 0.001) {
		EMISSION = albedo.rgb * glow;
	}
}
