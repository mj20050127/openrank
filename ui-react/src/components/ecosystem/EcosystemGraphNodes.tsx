import { useMemo } from 'react';
import * as THREE from 'three';
import SpriteText from 'three-spritetext';
import { nodeColor } from './graphVisualConfig';
import { stableHash } from './graphLayout';

const avatarTextureCache = new Map();
const chipTextureCache = new Map();

const REPOSITORY_LOGO_PATHS = Object.freeze({
  'microsoft/vscode': ['resources/win32/code_150x150.png'],
  'kubernetes/kubernetes': ['logo/logo.png'],
  'formatjs/formatjs': ['website/img/logo.svg', 'website/img/logo.png'],
  'odoo/odoo': ['addons/web/static/img/logo.png'],
});

function initials(value, limit = 3) {
  const name = String(value || '?').split('/').at(-1);
  return name.split(/[^a-zA-Z0-9]+/).filter(Boolean).map((part) => part[0]).join('').toUpperCase().slice(0, limit)
    || name.slice(0, limit).toUpperCase();
}

function configureTexture(texture) {
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = false;
  return texture;
}

function roundedRect(context, x, y, width, height, radius) {
  context.beginPath();
  context.roundRect(x, y, width, height, radius);
}

function drawAvatarFallback(context, label, fallbackColor) {
  context.clearRect(0, 0, 192, 192);
  context.fillStyle = fallbackColor;
  context.beginPath();
  context.arc(96, 96, 92, 0, Math.PI * 2);
  context.fill();
  context.fillStyle = '#FAF8F1';
  context.font = '700 54px system-ui, sans-serif';
  context.textAlign = 'center';
  context.textBaseline = 'middle';
  context.fillText(initials(label, 2), 96, 99);
}

function repositoryHealthStatus(node, hasHealth, health) {
  const explicit = String(node.health_status || node.healthStatus || '').toLowerCase();
  if (['risk', 'danger', 'critical'].includes(explicit)) return 'risk';
  if (['attention', 'warning', 'watch'].includes(explicit)) return 'attention';
  if (['healthy', 'good'].includes(explicit)) return 'healthy';
  if (!hasHealth) return 'unknown';
  if (health < 50) return 'risk';
  if (health < 70) return 'attention';
  return 'healthy';
}

function repositoryHealthColor(health, status) {
  if (status === 'risk') return '#B95643';
  if (status === 'attention') return '#B98332';
  if (!Number.isFinite(health)) return '#A9AEAA';
  return health >= 85 ? '#2F6F57' : '#4F876E';
}

function repositoryHealthLabel(status, hasHealth) {
  if (!hasHealth || status === 'unknown') return '暂无评分';
  if (status === 'risk') return '高风险';
  if (status === 'attention') return '需关注';
  return '健康';
}

function drawRepositoryStatusMark(context, color, x, y) {
  context.save();
  context.fillStyle = color;
  context.beginPath();
  context.arc(x, y, 10, 0, Math.PI * 2);
  context.fill();
  context.restore();
}

function drawConnectionAnchor(context, centerX, centerY, radius, angle) {
  const x = centerX + Math.cos(angle) * radius;
  const y = centerY + Math.sin(angle) * radius;
  context.save();
  context.fillStyle = '#174A3D';
  context.strokeStyle = '#FAF8F1';
  context.lineWidth = 3;
  context.beginPath();
  context.arc(x, y, 9, 0, Math.PI * 2);
  context.fill();
  context.stroke();
  context.restore();
}

function fitRepositoryName(context, value, maxWidth) {
  const text = String(value || 'repository');
  if (context.measureText(text).width <= maxWidth) return text;
  let end = text.length;
  while (end > 1 && context.measureText(`${text.slice(0, end)}…`).width > maxWidth) end -= 1;
  return `${text.slice(0, end)}…`;
}

function drawRepositoryFallback(context, centerX, centerY) {
  const gradient = context.createLinearGradient(centerX - 62, centerY - 58, centerX + 62, centerY + 58);
  gradient.addColorStop(0, '#2E68C8');
  gradient.addColorStop(1, '#2457A7');
  context.fillStyle = gradient;
  roundedRect(context, centerX - 62, centerY - 58, 43, 116, 4);
  context.fill();
  roundedRect(context, centerX - 8, centerY - 58, 70, 116, 4);
  context.fill();
  context.fillStyle = '#FAF8F1';
  [centerY - 36, centerY - 14, centerY + 8, centerY + 30].forEach((lineY, index) => {
    context.fillRect(centerX + (index === 0 ? 4 : 9), lineY, index === 0 ? 30 : 42, 8);
  });
}
function makeAvatarTexture(node, fallbackColor) {
  const primaryUrl = node.avatar_url || node.avatarUrl;
  const login = String(node.login || '').trim();
  const loginUrl = login ? `https://avatars.githubusercontent.com/${encodeURIComponent(login)}?s=192` : '';
  const urls = [...new Set([primaryUrl, loginUrl].filter(Boolean))];
  const cacheKey = urls.join('|') || `fallback:${login}`;
  if (avatarTextureCache.has(cacheKey)) return avatarTextureCache.get(cacheKey);
  const canvas = document.createElement('canvas');
  canvas.width = 192;
  canvas.height = 192;
  const context = canvas.getContext('2d');
  drawAvatarFallback(context, login, fallbackColor);
  const texture = configureTexture(new THREE.CanvasTexture(canvas));
  avatarTextureCache.set(cacheKey, texture);

  const loadAt = (index) => {
    if (index >= urls.length) return;
    const image = new Image();
    image.crossOrigin = 'anonymous';
    image.onload = () => {
      if (!image.naturalWidth || !image.naturalHeight) {
        loadAt(index + 1);
        return;
      }
      context.clearRect(0, 0, 192, 192);
      context.save();
      context.beginPath();
      context.arc(96, 96, 92, 0, Math.PI * 2);
      context.clip();
      const side = Math.min(image.naturalWidth, image.naturalHeight);
      context.drawImage(image, (image.naturalWidth - side) / 2, (image.naturalHeight - side) / 2, side, side, 0, 0, 192, 192);
      context.restore();
      texture.needsUpdate = true;
    };
    image.onerror = () => loadAt(index + 1);
    image.src = urls[index];
  };
  loadAt(0);
  return texture;
}

function makeChipTexture(node, root) {
  const repositoryName = String(node.repo || node.label || node.id || 'repository').replace(/^repo:/, '');
  const displayName = repositoryName.length > 26 ? `${repositoryName.slice(0, 25)}…` : repositoryName;
  const [owner = '', repo = ''] = repositoryName.split('/');
  const encodedRepository = [owner, repo].map(encodeURIComponent).join('/');
  const branch = encodeURIComponent(String(node.default_branch || 'main'));
  const rawBase = owner && repo ? `https://raw.githubusercontent.com/${encodedRepository}/${branch}/` : '';
  const explicitImageUrl = node.repository_avatar_url || node.repositoryAvatarUrl || node.logo_url || node.logoUrl || node.open_graph_image_url || node.openGraphImageUrl;
  const preferredPaths = REPOSITORY_LOGO_PATHS[repositoryName.toLowerCase()] || [];
  const conventionalPaths = ['.github/logo.png', 'logo.png', 'logo/logo.png', 'docs/logo.png', 'docs/images/logo.png', 'assets/logo.png'];
  const repositoryImageUrls = [...new Set([
    explicitImageUrl,
    ...preferredPaths.map((assetPath) => rawBase + assetPath),
    ...conventionalPaths.map((assetPath) => rawBase + assetPath),
    owner && repo ? `https://opengraph.githubassets.com/1/${encodedRepository}` : '',
  ].filter(Boolean))];
  const rawHealth = Number(node.health_score ?? node.healthScore ?? node.score);
  const hasHealth = Number.isFinite(rawHealth);
  const health = hasHealth ? Math.max(0, Math.min(100, rawHealth)) : 0;
  const healthStatus = repositoryHealthStatus(node, hasHealth, health);
  const healthColor = repositoryHealthColor(hasHealth ? health : Number.NaN, healthStatus);
  const key = `${root ? 'root' : 'related'}:${repositoryName}:${node.language || ''}:${node.stars || 0}:${health}:${healthStatus}:${repositoryImageUrls.join('|')}`;
  if (chipTextureCache.has(key)) return chipTextureCache.get(key);
  const canvas = document.createElement('canvas');
  const textureScale = root ? 2 : 1;
  const width = root ? 560 : 640;
  const height = root ? 560 : 180;
  canvas.width = width * textureScale;
  canvas.height = height * textureScale;
  const context = canvas.getContext('2d');
  context.scale(textureScale, textureScale);
  if (!root) {
    roundedRect(context, 14, 14, width - 28, height - 28, 4);
    context.fillStyle = '#FAF8F1';
    context.fill();
    context.lineWidth = 2;
    context.strokeStyle = '#9FA9A3';
    context.stroke();
  }

  let avatarBox;
  if (root) {
    const ringCenterX = width / 2;
    const ringCenterY = height / 2;
    const outerRadius = 258;
    const middleRadius = 246;
    const innerRadius = 225;

    context.beginPath();
    context.arc(ringCenterX, ringCenterY, outerRadius, 0, Math.PI * 2);
    context.fillStyle = '#FAF8F1';
    context.fill();
    context.lineWidth = 1.5;
    context.strokeStyle = '#88A9E2';
    context.stroke();

    context.beginPath();
    context.arc(ringCenterX, ringCenterY, middleRadius, 0, Math.PI * 2);
    context.lineWidth = 4;
    context.strokeStyle = '#174A3D';
    context.stroke();

    context.beginPath();
    context.arc(ringCenterX, ringCenterY, innerRadius, 0, Math.PI * 2);
    context.lineWidth = 3.5;
    context.strokeStyle = '#2E66B7';
    context.stroke();

    [-Math.PI * 0.76, Math.PI, 0, Math.PI * 0.24].forEach((angle) => {
      drawConnectionAnchor(context, ringCenterX, ringCenterY, middleRadius, angle);
    });

    context.textAlign = 'left';
    context.textBaseline = 'alphabetic';
    context.fillStyle = '#174A3D';
    context.font = '600 30px Consolas, monospace';
    context.fillText('R01', 176, 148);
    drawRepositoryStatusMark(context, healthColor, 374, 140);

    avatarBox = { x: 210, y: 166, width: 140, height: 124, radius: 0 };
    drawRepositoryFallback(context, ringCenterX, 228);

    context.textAlign = 'center';
    context.textBaseline = 'alphabetic';
    context.fillStyle = '#174A3D';
    context.font = '700 31px Consolas, monospace';
    context.fillText(fitRepositoryName(context, repositoryName, 410), ringCenterX, 350);

    const scoreLabel = hasHealth ? health.toFixed(1) : '—';
    context.font = '700 76px Consolas, monospace';
    const scoreWidth = context.measureText(scoreLabel).width;
    context.font = '500 28px Consolas, monospace';
    const unitWidth = hasHealth ? context.measureText('/100').width : 0;
    const scoreStart = (width - scoreWidth - (hasHealth ? unitWidth + 12 : 0)) / 2;
    context.textAlign = 'left';
    context.fillStyle = '#174A3D';
    context.font = '700 76px Consolas, monospace';
    context.fillText(scoreLabel, scoreStart, 435);
    if (hasHealth) {
      context.fillStyle = '#174A3D';
      context.font = '500 28px Consolas, monospace';
      context.fillText('/100', scoreStart + scoreWidth + 12, 432);
    }
    context.textAlign = 'center';
    context.fillStyle = healthColor;
    context.font = '500 25px system-ui, sans-serif';
    context.fillText(repositoryHealthLabel(healthStatus, hasHealth), ringCenterX, 486);
  } else {
    const logoGradient = context.createLinearGradient(34, 38, 142, 142);
    logoGradient.addColorStop(0, '#42679A');
    logoGradient.addColorStop(1, '#34765F');
    avatarBox = { x: 34, y: 36, width: 108, height: 108, radius: 4 };
    roundedRect(context, avatarBox.x, avatarBox.y, avatarBox.width, avatarBox.height, avatarBox.radius);
    context.fillStyle = logoGradient;
    context.fill();
    context.fillStyle = '#FAF8F1';
    context.font = '800 42px system-ui, sans-serif';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(initials(repositoryName, 2), 88, 92);    context.textAlign = 'left';
    context.textBaseline = 'alphabetic';
    context.fillStyle = '#172A25';
    context.font = '700 31px system-ui, sans-serif';
    context.fillText(displayName, 170, 75);
    context.fillStyle = '#66756E';
    context.font = '500 22px system-ui, sans-serif';
    context.fillText(`★ ${Number(node.stars || 0).toLocaleString()}   ·   ${node.language || '语言未知'}`, 170, 116);
  }

  const texture = configureTexture(new THREE.CanvasTexture(canvas));
  chipTextureCache.set(key, texture);
  const loadRepositoryImage = (index) => {
    if (index >= repositoryImageUrls.length) return;
    const image = new Image();
    image.crossOrigin = 'anonymous';
    image.onload = () => {
      if (!image.naturalWidth || !image.naturalHeight) {
        loadRepositoryImage(index + 1);
        return;
      }
      context.save();
      if (!root) {
        roundedRect(context, avatarBox.x, avatarBox.y, avatarBox.width, avatarBox.height, avatarBox.radius);
        context.clip();
      }
      const scale = root
        ? Math.min(avatarBox.width / image.naturalWidth, avatarBox.height / image.naturalHeight)
        : Math.max(avatarBox.width / image.naturalWidth, avatarBox.height / image.naturalHeight);
      const drawWidth = image.naturalWidth * scale;
      const drawHeight = image.naturalHeight * scale;
      context.drawImage(image, avatarBox.x + (avatarBox.width - drawWidth) / 2, avatarBox.y + (avatarBox.height - drawHeight) / 2, drawWidth, drawHeight);
      context.restore();
      if (!root) {
        context.lineWidth = 2;
        context.strokeStyle = '#9FA9A3';
        roundedRect(context, avatarBox.x, avatarBox.y, avatarBox.width, avatarBox.height, avatarBox.radius);
        context.stroke();
      }
      texture.needsUpdate = true;
    };
    image.onerror = () => loadRepositoryImage(index + 1);
    image.src = repositoryImageUrls[index];
  };
  loadRepositoryImage(0);
  return texture;
}function addLoadingArc(group, radius) {
  const curve = new THREE.EllipseCurve(0, 0, radius * 1.23, radius * 1.23, 0.15, Math.PI * 1.55, false, 0);
  const line = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(curve.getPoints(36).map((point) => new THREE.Vector3(point.x, point.y, 0))),
    new THREE.LineDashedMaterial({ color: '#3978F6', dashSize: 1, gapSize: 0.75, transparent: true, opacity: 0.78, depthTest: false }),
  );
  line.computeLineDistances();
  line.renderOrder = 22;
  line.onBeforeRender = () => { line.rotation.z += 0.012; };
  group.add(line);
}

function addStatusBadge(group, radius, kind) {
  const risk = kind === 'risk';
  const badgeRadius = Math.min(2.1, Math.max(1.35, radius * 0.22));
  const badge = new THREE.Mesh(
    new THREE.CircleGeometry(badgeRadius, 28),
    new THREE.MeshBasicMaterial({ color: risk ? '#EF6969' : '#26B879', transparent: true, opacity: 1, depthTest: false }),
  );
  badge.position.set(radius * 0.7, radius * 0.72, 1.4);
  badge.renderOrder = 18;
  group.add(badge);
  if (risk) {
    const mark = new SpriteText('!');
    mark.color = '#FFFFFF';
    mark.textHeight = badgeRadius * 1.18;
    mark.position.set(radius * 0.7, radius * 0.69, 1.8);
    mark.material.depthTest = false;
    mark.renderOrder = 19;
    group.add(mark);
  }
}

function addBridgeBadge(group, radius) {
  const bridge = new SpriteText('↔');
  bridge.color = '#6675E8';
  bridge.backgroundColor = 'rgba(255,255,255,.94)';
  bridge.padding = 0.8;
  bridge.borderRadius = 3;
  bridge.textHeight = Math.max(1.5, radius * 0.27);
  bridge.position.set(-radius * 0.72, -radius * 0.7, 1.2);
  bridge.material.depthTest = false;
  bridge.renderOrder = 18;
  group.add(bridge);
}

function RepositoryNodeRenderer({ node, radius, opacity }) {
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
    map: makeChipTexture(node, Boolean(node.is_root)), transparent: true, opacity, depthTest: false, depthWrite: false,
  }));
  const width = node.is_root ? radius * 2.42 : radius * (node.parent_id ? 8.6 : 12.4);
  const aspect = node.is_root ? 1 : 3.7;
  sprite.scale.set(width, width / aspect, 1);
  sprite.renderOrder = node.is_root ? 18 : 10;
  return sprite;
}

function ContributorNodeRenderer({ node, radius, opacity, color }) {
  const group = new THREE.Group();
  const faceRadius = radius;
  if (node.avatar_url || node.avatarUrl || node.login) {
    const avatar = new THREE.Sprite(new THREE.SpriteMaterial({
      map: makeAvatarTexture(node, color), transparent: true, opacity, depthTest: false, depthWrite: false,
    }));
    avatar.scale.set(faceRadius * 1.82, faceRadius * 1.82, 1);
    avatar.renderOrder = 10;
    group.add(avatar);
  } else {
    const fallback = new THREE.Mesh(
      new THREE.CircleGeometry(faceRadius * 0.91, 40),
      new THREE.MeshBasicMaterial({ color: '#DDE3DE', transparent: true, opacity, depthTest: false }),
    );
    fallback.renderOrder = 10;
    group.add(fallback);
    const mark = new SpriteText(initials(node.login, 2));
    mark.color = '#43524C';
    mark.textHeight = faceRadius * 0.58;
    mark.material.depthTest = false;
    mark.renderOrder = 16;
    group.add(mark);
  }

  const roleRing = new THREE.Mesh(
    new THREE.RingGeometry(faceRadius * 0.93, faceRadius, 56),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity, side: THREE.DoubleSide, depthTest: false }),
  );
  roleRing.renderOrder = 15;
  group.add(roleRing);

  const strengthTrack = new THREE.Mesh(
    new THREE.RingGeometry(faceRadius * 1.055, faceRadius * 1.085, 56),
    new THREE.MeshBasicMaterial({ color: '#B7BBB3', transparent: true, opacity: opacity * 0.58, side: THREE.DoubleSide, depthTest: false }),
  );
  strengthTrack.renderOrder = 14;
  group.add(strengthTrack);
  const normalized = Math.max(0.04, Math.min(1, Number(node.contributionNormalized || 0)));
  const strengthOuter = faceRadius * (1.078 + normalized * 0.018);
  const strengthInner = faceRadius * (1.05 - normalized * 0.025);
  const strengthArc = new THREE.Mesh(
    new THREE.RingGeometry(strengthInner, strengthOuter, 56, 1, Math.PI / 2, Math.PI * 2 * normalized),
    new THREE.MeshBasicMaterial({ color: '#172A25', transparent: true, opacity: opacity * 0.82, side: THREE.DoubleSide, depthTest: false }),
  );
  strengthArc.renderOrder = 16;
  group.add(strengthArc);

  if (node.role === 'new') addStatusBadge(group, faceRadius, 'new');
  if (node.risk || node.churn_risk || node.role === 'risk') addStatusBadge(group, faceRadius, 'risk');
  if (node.is_bridge) addBridgeBadge(group, faceRadius);
  return group;
}
function CommunityZoneRenderer(node) {
  const group = new THREE.Group();
  const samples = Array.isArray(node.samples) ? node.samples : [];
  const contours = Array.isArray(node.contours) ? node.contours : [];
  const bounds = node.densityBounds || {
    minX: -node.radiusX,
    minY: -node.radiusY,
    maxX: node.radiusX,
    maxY: node.radiusY,
  };
  const focusFactor = node.communityState === 'focused' ? 1.3 : node.communityState === 'dimmed' ? 0.62 : 1;

  samples.forEach((sample) => {
    const haloRadius = Math.max(26, Number(node.bandwidth || 48) * (0.58 + Math.min(1, Math.sqrt(Math.max(0, Number(sample.weight) || 0)) / 28) * 0.25));
    const halo = new THREE.Mesh(
      new THREE.CircleGeometry(haloRadius, 36),
      new THREE.MeshBasicMaterial({ color: node.fill, transparent: true, opacity: 0.024 * focusFactor, depthWrite: false, depthTest: false, side: THREE.DoubleSide }),
    );
    halo.position.set(sample.x, sample.y, -4);
    halo.renderOrder = 0;
    halo.raycast = () => {};
    group.add(halo);
  });

  contours.forEach((level, levelIndex) => {
    const coordinates = [];
    for (const segment of level.segments || []) {
      coordinates.push(
        segment[0][0], segment[0][1], -3.9 + levelIndex * 0.01,
        segment[1][0], segment[1][1], -3.9 + levelIndex * 0.01,
      );
    }
    if (!coordinates.length) return;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(coordinates, 3));
    const line = new THREE.LineSegments(
      geometry,
      new THREE.LineBasicMaterial({
        color: node.stroke,
        opacity: Number(level.opacity || 0.16) * focusFactor,
        linewidth: Number(level.lineWidth || 0.75),
        transparent: true,
        depthTest: false,
      }),
    );
    line.renderOrder = 1;
    line.raycast = () => {};
    group.add(line);
  });

  const labelRows = String(node.label || '').split('\n');
  const title = new SpriteText(labelRows[0] || '');
  title.color = node.stroke;
  title.textHeight = 10.5;
  title.fontWeight = '700';
  title.position.set(bounds.minX + 48, bounds.maxY + 14, -3.5);
  title.material.depthTest = false;
  title.renderOrder = 2;
  title.raycast = () => {};
  group.add(title);

  if (labelRows[1]) {
    const subtitle = new SpriteText(labelRows[1]);
    subtitle.color = node.stroke;
    subtitle.textHeight = 8;
    subtitle.fontWeight = '600';
    subtitle.position.set(bounds.minX + 48, bounds.maxY + 2, -3.5);
    subtitle.material.depthTest = false;
    subtitle.renderOrder = 2;
    subtitle.raycast = () => {};
    group.add(subtitle);
  }
  return group;
}
function RoutingJunctionRenderer(node, radius, opacity) {
  const group = new THREE.Group();
  const dotRadius = Math.max(3.5, Math.min(6, Number(radius) || 5));
  const halo = new THREE.Mesh(
    new THREE.CircleGeometry(dotRadius * 1.65, 32),
    new THREE.MeshBasicMaterial({ color: '#F5F1E7', transparent: true, opacity: 0.82 * opacity, depthTest: false, depthWrite: false }),
  );
  halo.position.z = 0.1;
  halo.renderOrder = 18;
  halo.raycast = () => {};
  group.add(halo);
  const dot = new THREE.Mesh(
    new THREE.CircleGeometry(dotRadius, 32),
    new THREE.MeshBasicMaterial({ color: node.fill || '#66756E', transparent: true, opacity: 0.96 * opacity, depthTest: false, depthWrite: false }),
  );
  dot.position.z = 0.2;
  dot.renderOrder = 19;
  dot.raycast = () => {};
  group.add(dot);
  return group;
}
function addExpandedRepositoryRoutes(group, targets, radius, opacity) {
  if (!Array.isArray(targets) || !targets.length) return;
  const validTargets = targets.filter((target) => Number.isFinite(Number(target.x)) && Number.isFinite(Number(target.y)));
  if (!validTargets.length) return;
  const average = validTargets.reduce((position, target) => ({
    x: position.x + Number(target.x) / validTargets.length,
    y: position.y + Number(target.y) / validTargets.length,
  }), { x: 0, y: 0 });
  const junction = new THREE.Vector3(average.x * 0.44, average.y * 0.44, 0.35);
  const distance = Math.hypot(junction.x, junction.y) || 1;
  const start = new THREE.Vector3(
    junction.x / distance * radius * 1.22,
    junction.y / distance * radius * 1.22,
    0.35,
  );
  const addCurve = (from, to, bend = 0) => {
    const deltaX = to.x - from.x;
    const deltaY = to.y - from.y;
    const length = Math.hypot(deltaX, deltaY) || 1;
    const control = new THREE.Vector3(
      (from.x + to.x) / 2 - deltaY / length * bend,
      (from.y + to.y) / 2 + deltaX / length * bend,
      0.35,
    );
    const curve = new THREE.QuadraticBezierCurve3(from, control, to);
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(curve.getPoints(32)),
      new THREE.LineBasicMaterial({ color: '#315B9A', transparent: true, opacity: 0.92 * opacity, depthTest: false, depthWrite: false }),
    );
    line.renderOrder = 9;
    line.raycast = () => {};
    group.add(line);
  };
  addCurve(start, junction);
  validTargets.forEach((target, index) => {
    const end = new THREE.Vector3(Number(target.x), Number(target.y), 0.35);
    addCurve(junction, end);
  });
  const junctionDot = new THREE.Mesh(
    new THREE.CircleGeometry(3.5, 28),
    new THREE.MeshBasicMaterial({ color: '#315B9A', transparent: true, opacity: 0.96 * opacity, depthTest: false, depthWrite: false }),
  );
  junctionDot.position.copy(junction);
  junctionDot.renderOrder = 10;
  junctionDot.raycast = () => {};
  group.add(junctionDot);
}
function buildFlatNodeObject(node, radius, opacity, selected, hovered, loading, collapsing, _pulseToken) {
  if (node.visualType === 'community-zone') return CommunityZoneRenderer(node);

  if (node.visualType === 'routing-junction' || node.type === 'routing-junction') return RoutingJunctionRenderer(node, radius, opacity);
  if (node.visualType === 'edge-hub' || node.type === 'edge-hub') return new THREE.Group();
  const group = new THREE.Group();
  const color = nodeColor(node);
  const materialOpacity = opacity * (collapsing ? 0.08 : 1);
  const isRoot = node.visualType === 'root-repository' || node.is_root;
  const isRepository = isRoot || node.visualType === 'repository' || node.type === 'repository' || node.type === 'root-repository';
  if (!isRepository && node.__expandedRouteTargets?.length) {
    addExpandedRepositoryRoutes(group, node.__expandedRouteTargets, radius, materialOpacity);
  }
  const body = isRepository
    ? RepositoryNodeRenderer({ node, radius, opacity: materialOpacity })
    : ContributorNodeRenderer({ node, radius, opacity: materialOpacity, color });
  group.add(body);

  if (selected || hovered) {
    if (isRepository) {
      const width = isRoot ? radius * 2.42 : radius * (node.parent_id ? 8.9 : 12.7);
      const height = isRoot ? width : width / 3.7;
      if (isRoot) {
        const selectionHalo = new THREE.Mesh(
          new THREE.RingGeometry(width / 2 + 1.4, width / 2 + 3.4, 72),
          new THREE.MeshBasicMaterial({ color: selected ? '#315B9A' : '#34765F', transparent: true, opacity: selected ? 0.82 : 0.52, depthTest: false, depthWrite: false, side: THREE.DoubleSide }),
        );
        selectionHalo.position.z = -0.1;
        selectionHalo.renderOrder = 17;
        selectionHalo.raycast = () => {};
        group.add(selectionHalo);
      } else {
        const selectionHalo = new THREE.Mesh(
          new THREE.PlaneGeometry(width + 8, height + 8),
          new THREE.MeshBasicMaterial({ color: selected ? '#315B9A' : '#34765F', transparent: true, opacity: selected ? 0.16 : 0.09, depthTest: false, depthWrite: false, side: THREE.DoubleSide }),
        );
        selectionHalo.position.z = -0.15;
        selectionHalo.renderOrder = 17;
        selectionHalo.raycast = () => {};
        group.add(selectionHalo);

        const points = [
          new THREE.Vector3(-width / 2, -height / 2, 1.2),
          new THREE.Vector3(width / 2, -height / 2, 1.2),
          new THREE.Vector3(width / 2, height / 2, 1.2),
          new THREE.Vector3(-width / 2, height / 2, 1.2),
        ];
        const outline = new THREE.LineLoop(
          new THREE.BufferGeometry().setFromPoints(points),
          new THREE.LineBasicMaterial({ color: selected ? '#315B9A' : '#34765F', transparent: true, opacity: selected ? 0.96 : 0.68, depthTest: false }),
        );
        outline.renderOrder = 22;
        group.add(outline);
      }
    } else {
      const interactionRing = new THREE.Mesh(
        new THREE.RingGeometry(radius * 1.15, radius * 1.19, 56),
        new THREE.MeshBasicMaterial({ color: selected ? '#315B9A' : '#34765F', transparent: true, opacity: selected ? 0.96 : 0.68, side: THREE.DoubleSide, depthTest: false }),
      );
      interactionRing.renderOrder = 22;
      group.add(interactionRing);
    }
  }
  const effectRadius = isRepository ? radius * 1.2 : radius * 1.35;
  if (loading) addLoadingArc(group, effectRadius);
  if (hovered && isRoot) group.scale.setScalar(1.035);
  if (selected && !isRoot) group.scale.setScalar(1.035);
  else if (hovered && !isRoot) group.scale.setScalar(1.06);
  if (collapsing) group.scale.setScalar(0.45);
  return group;
}
export function FlatReagraphNode({ node, size, opacity, selected }) {
  const data = node.data;
  const renderSize = Number(data.visualSize || size);
  const effectiveOpacity = data.__dimmed ? Math.min(opacity, 0.18) : opacity;
  const object = useMemo(
    () => buildFlatNodeObject(data, renderSize, effectiveOpacity, selected || data.__relatedHighlight, data.__hovered, data.__loading, data.__collapsing, data.__selectionPulse),
    [data, renderSize, effectiveOpacity, selected],
  );
  return <primitive object={object} />;
}
export function FlatReagraphCluster({ outerRadius, padding, opacity = 0.055, label }) {
  const radius = Math.max(14, outerRadius + Math.min(padding, 10));
  const clusterKey = String(label?.text || 'active').toLowerCase();
  const color = clusterKey.includes('core') ? '#267DFF' : clusterKey.includes('lifecycle') ? '#8067E8' : '#19A7A7';
  const clusterLabel = clusterKey.includes('core') ? '核心维护者' : clusterKey.includes('lifecycle') ? '新晋与流失风险' : '活跃贡献者';
  const object = useMemo(() => {
    const group = new THREE.Group();
    const material = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: Math.min(0.065, Math.max(0.035, opacity)),
      depthWrite: false,
      depthTest: false,
      side: THREE.DoubleSide,
    });
    const fill = new THREE.Mesh(new THREE.CircleGeometry(radius, 64), material);
    fill.position.z = -1; fill.scale.set(1, 0.68, 1); fill.renderOrder = 1; group.add(fill);
    const curve = new THREE.EllipseCurve(0, 0, radius, radius * 0.68, 0, Math.PI * 2);
    const outline = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(curve.getPoints(80).map((point) => new THREE.Vector3(point.x, point.y, -0.5))),
      new THREE.LineDashedMaterial({ color, dashSize: 5, gapSize: 3, opacity: 0.42, transparent: true, depthTest: false }),
    );
    outline.computeLineDistances(); outline.renderOrder = 2; group.add(outline);
    const title = new SpriteText(clusterLabel);
    title.color = color; title.textHeight = 7; title.fontWeight = '700';
    title.backgroundColor = 'rgba(246,250,254,.82)'; title.padding = 2.5; title.borderRadius = 4;
    title.position.set(-radius * 0.66, radius * 0.62, 1); title.material.depthTest = false; title.renderOrder = 3; group.add(title);
    group.visible = outerRadius > 12;
    return group;
  }, [radius, opacity, color, outerRadius, clusterLabel]);
  return <primitive object={object} />;
}









