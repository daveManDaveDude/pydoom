#version 120
varying vec2 vUV;
uniform sampler2D uWallTex;
void main() {
    gl_FragColor = texture2D(uWallTex, vUV);
}