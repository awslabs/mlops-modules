import { createHash } from 'crypto';

function generateHash(input: string, length: number): string {
  return createHash('md5').update(input).digest('hex').slice(0, length);
}

/**
 * Generate a unique resource name by combining given name and a hash of the name.
 * @param name - A unique readable resource name. Used as a prefix and truncated if it exceeds maxLength.
 * @param maxLength - The maximum length of the resource name
 * @returns A unique resource name that is no longer than maxLength
 */
export function createResourceName(name: string, maxLength: number): string {
  name = removeNonAllowedSpecialCharacters(name);
  const hashLength = 8;
  const hash = generateHash(name, hashLength);
  const prefixLength = maxLength - hashLength - 1; // -1 for the separator
  const prefix = name.slice(0, prefixLength);
  return `${prefix}-${hash}`;
}

/**
 * Removes all non-allowed special characters in a string.
 */
function removeNonAllowedSpecialCharacters(s: string) {
  const pattern = '[^A-Za-z0-9-_]';
  const regex = new RegExp(pattern, 'g');
  return s.replace(regex, '');
}
