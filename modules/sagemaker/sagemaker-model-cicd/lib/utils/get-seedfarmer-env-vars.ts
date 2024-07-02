export function getSeedFarmerEnvVars() {
  // get all environment variables starting with SEEDFARMER_
  const seedFarmerEnvVars = Object.keys(process.env).reduce(
    (acc, key) => {
      if (key.startsWith('SEEDFARMER_')) {
        acc[key] = process.env[key] || '';
      }
      return acc;
    },
    {} as Record<string, string>,
  );
  return seedFarmerEnvVars;
}
