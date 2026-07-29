import api from "./api";

/**
 * Fetch settings from database
 * @returns {Promise<object>} Settings data
 */
export const getSettings = async () => {
  const response = await api.get("/api/settings");
  return response.data.data;
};

/**
 * Update settings in database
 * @param {object} settings
 * @returns {Promise<object>} Updated settings data
 */
export const updateSettings = async (settings) => {
  const response = await api.put("/api/settings", settings);
  return response.data.data;
};
