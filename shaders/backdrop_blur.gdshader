shader_type canvas_item;

uniform sampler2D screen_texture : hint_screen_texture, repeat_disable, filter_linear;
uniform float blur_amount : hint_range(0.0, 6.0) = 2.5;
uniform float darken : hint_range(0.0, 1.0) = 0.55;
uniform vec4 tint : source_color = vec4(0.035, 0.05, 0.045, 1.0);

void fragment() {
	vec2 uv = SCREEN_UV;
	vec2 px = SCREEN_PIXEL_SIZE * blur_amount;
	vec3 c = texture(screen_texture, uv).rgb * 0.28;
	c += texture(screen_texture, uv + vec2(px.x, 0.0)).rgb * 0.14;
	c += texture(screen_texture, uv - vec2(px.x, 0.0)).rgb * 0.14;
	c += texture(screen_texture, uv + vec2(0.0, px.y)).rgb * 0.14;
	c += texture(screen_texture, uv - vec2(0.0, px.y)).rgb * 0.14;
	c += texture(screen_texture, uv + px).rgb * 0.08;
	c += texture(screen_texture, uv - px).rgb * 0.08;
	c *= darken;
	c = mix(c, tint.rgb, 0.22);
	COLOR = vec4(c, 1.0);
}
