shader_type canvas_item;

uniform sampler2D screen_texture : hint_screen_texture, repeat_disable, filter_linear;
uniform float vignette : hint_range(0.0, 1.0) = 0.4;
uniform float grain : hint_range(0.0, 0.2) = 0.03;
uniform float warmth : hint_range(-1.0, 1.0) = 0.0;
uniform float desat : hint_range(0.0, 1.0) = 0.0;

float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

void fragment() {
	vec2 uv = SCREEN_UV;
	vec3 col = texture(screen_texture, uv).rgb;

	float d = distance(uv, vec2(0.5));
	col *= 1.0 - smoothstep(0.32, 0.9, d) * vignette;

	float lum = dot(col, vec3(0.299, 0.587, 0.114));
	col = mix(vec3(lum), col, 1.0 - desat);
	col *= mix(vec3(0.95, 0.97, 1.0), vec3(1.04, 1.0, 0.94), clamp(warmth * 0.5 + 0.5, 0.0, 1.0));

	float g = hash21(uv * vec2(1920.0, 1080.0) + fract(TIME) * 71.0) - 0.5;
	col += g * grain;

	COLOR = vec4(col, 1.0);
}
