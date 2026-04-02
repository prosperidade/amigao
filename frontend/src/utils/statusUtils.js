export const getStatusStyle = (value, threshold, comparison) => {
  const isOk = comparison === 'greater' ? value > threshold : value < threshold;
  return isOk ? "status-ok" : "status-alert";
};
