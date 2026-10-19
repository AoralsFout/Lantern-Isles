shader_type sky;

uniform vec3 top_color : source_color = vec3(0.32, 0.48, 0.52);
uniform vec3 horizon_color : source_color = vec3(0.86, 0.78, 0.62);
uniform vec3 bottom_color : source_color = vec3(0.2, 0.27, 0.29);
uniform vec3 cloud_color : source_color = vec3(0.95, 0.9, 0.83);
uniform vec3 sun_color : source_color = vec3(1.0, 0.86, 0.62);
uniform vec3 sun_direction = vec3(0.45, 0.32, -0.83);
uniform float sun_glow : hint_range(0.0, 3.0) = 1.0;
uniform float star_amount : hint_range(0.0, 1.0) = 0.0;
uniform float aurora_amount : hint_range(0.0, 1.0) = 0.0;
uniform float cloud_amount : hint_range(0.0, 1.0) = 0.28;
uniform float horizon_softness : hint_range(0.01, 1.0) = 0.5;

float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float value_noise(vec2 p) {
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
		v += a * value_noise(p);
		p = p * 2.03 + vec2(13.7, 7.3);
		a *= 0.5;
	}
	return v;
}

void sky() {
	vec3 d = normalize(EYEDIR);
	float h = clamp(d.y, -0.2, 1.0);

	vec3 col = mix(bottom_color, horizon_color, smoothstep(-0.12, 0.12, h));
	col = mix(col, top_color, smoothstep(0.02, 0.72, h));

	// sun disc + broad warm haze
	vec3 sdir = normalize(sun_direction);
	float sd = max(dot(d, sdir), 0.0);
	col += sun_color * pow(sd, 900.0) * 2.4 * sun_glow;
	col += sun_color * pow(sd, 22.0) * 0.16 * sun_glow;
	col += sun_color * pow(sd, 4.0) * 0.04 * sun_glow;

	// stars (stable in world space, faintly twinkling)
	if (star_amount > 0.001) {
		vec2 sp = d.xz / (abs(d.y) + 0.36) * 34.0;
		vec2 cell = floor(sp);
		float rnd = hash21(cell);
		float dist = length(fract(sp) - vec2(0.5));
		float twinkle = 0.55 + 0.45 * sin(TIME * (0.7 + rnd * 2.0) + rnd * 40.0);
		float star = step(0.983, rnd) * smoothstep(0.18, 0.0, dist) * twinkle;
		float star2 = step(0.997, rnd) * smoothstep(0.26, 0.0, dist) * 2.0;
		col += mix(vec3(0.72, 0.88, 1.0), vec3(1.0, 0.86, 0.62), rnd) * (star + star2) * star_amount * 1.7 * smoothstep(0.0, 0.18, d.y);
	}

	// aurora ribbons
	if (aurora_amount > 0.001) {
		float wx = d.x * 2.4 + d.z * 1.4;
		float ribbon = sin(wx * 2.2 + TIME * 0.035) * 0.5 + 0.5;
		ribbon *= sin(wx * 5.1 - TIME * 0.02 + 1.7) * 0.5 + 0.5;
		ribbon = pow(ribbon, 3.0);
		float band = smoothstep(0.08, 0.35, d.y) * (1.0 - smoothstep(0.55, 0.9, d.y));
		col += mix(vec3(0.22, 0.86, 0.72), vec3(0.5, 0.55, 1.0), fbm(d.xz * 2.0)) * ribbon * band * aurora_amount * 0.55;
	}

	// soft high cloud bands, kept away from the sun disc
	if (cloud_amount > 0.001) {
		vec2 cp = vec2(atan(d.z, d.x) * 2.4, d.y * 7.0 + TIME * 0.006);
		float cl = fbm(cp * vec2(1.0, 1.5) + 4.2);
		cl = smoothstep(0.5, 0.84, cl);
		float mask = smoothstep(0.0, 0.22, d.y) * (1.0 - smoothstep(0.35, 0.9, d.y));
		col = mix(col, cloud_color, cl * mask * cloud_amount * 0.55);
	}

	// deep horizon glow and gentle dithering to avoid banding
	col += horizon_color * 0.035 * (1.0 - smoothstep(0.0, 0.16, abs(d.y)));
	col += (hash21(FRAGCOORD.xy + TIME) - 0.5) * 0.006;
	COLOR = col;
}
