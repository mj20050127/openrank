import { lightTheme } from 'reagraph';

export const ecosystemLightTheme = {
  ...lightTheme,
  canvas: { background: '#F3F0E7', fog: '#F3F0E7' },
  node: {
    ...lightTheme.node,
    fill: '#34755F',
    activeFill: '#14231F',
    opacity: 0.98,
    selectedOpacity: 1,
    inactiveOpacity: 0.2,
    label: {
      ...lightTheme.node.label,
      color: '#14231F',
      activeColor: '#14231F',
      backgroundColor: '#FAF8F1',
      backgroundOpacity: 0.92,
      padding: 4,
      radius: 1,
    },
  },
  ring: { fill: '#718079', activeFill: '#14231F' },
  cluster: { fill: '#88AC94', opacity: 0.04, selectedOpacity: 0.07, inactiveOpacity: 0.02, label: { color: '#43524C', stroke: '#FAF8F1', fontSize: 10 } },
  edge: {
    ...lightTheme.edge,
    fill: '#8DA096',
    activeFill: '#14231F',
    opacity: 0.58,
    selectedOpacity: 0.88,
    inactiveOpacity: 0.04,
  },
  arrow: { fill: '#8DA096', activeFill: '#14231F' },
};
export const lightTechnologyTheme = ecosystemLightTheme;
