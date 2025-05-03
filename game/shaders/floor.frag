#version 120
varying vec2 vUV;
uniform vec2 uRes;
uniform vec2 uPos;
uniform float uAng;
uniform float uHalfFov;
uniform float uPitch;
uniform sampler2D uFloorTex;
uniform sampler2D uCeilTex;
void main() {
    float fx = gl_FragCoord.x / uRes.x;
    float horizon = uRes.y * 0.5 + uPitch;
    if (gl_FragCoord.y < horizon) {
        float rowDist = (uRes.y * 0.5) / abs(gl_FragCoord.y - horizon);
        float cosA = cos(uAng);
        float sinA = sin(uAng);
        float planeX = -sinA * tan(uHalfFov);
        float planeY = cosA * tan(uHalfFov);
        vec2 dir0 = vec2(cosA - planeX, sinA - planeY);
        vec2 dir1 = vec2(cosA + planeX, sinA + planeY);
        vec2 pos = uPos + rowDist * (dir0 + fx * (dir1 - dir0));
        vec2 texUV = fract(pos);
        gl_FragColor = texture2D(uFloorTex, texUV);
    } else {
        float rowDist = (uRes.y * 0.5) / abs(gl_FragCoord.y - horizon);
        float cosA = cos(uAng);
        float sinA = sin(uAng);
        float planeX = -sinA * tan(uHalfFov);
        float planeY = cosA * tan(uHalfFov);
        vec2 dir0 = vec2(cosA - planeX, sinA - planeY);
        vec2 dir1 = vec2(cosA + planeX, sinA + planeY);
        vec2 pos = uPos + rowDist * (dir0 + fx * (dir1 - dir0));
        vec2 texUV = fract(pos);
        gl_FragColor = texture2D(uCeilTex, texUV);
    }
}