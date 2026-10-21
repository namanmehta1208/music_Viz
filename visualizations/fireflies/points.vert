#version 330

// One firefly per point; fireflies/__init__.py fills these every frame.
in vec2 in_position;   // 0..1 across the screen
in float in_size;      // diameter in pixels
in vec3 in_color;      // already multiplied by its brightness

out vec3 color;

void main() {
    gl_Position = vec4(in_position * 2.0 - 1.0, 0.0, 1.0);
    gl_PointSize = in_size;
    color = in_color;
}
