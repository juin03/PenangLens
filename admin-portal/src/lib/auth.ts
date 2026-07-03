import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { NextRequest } from 'next/server';
import { prisma } from './prisma';

const TOKEN_EXPIRE = '24h';

// No fallback secret: signing tokens with a value published in the repo would let
// anyone forge admin sessions. Checked lazily so `next build` works without env vars.
function getJwtSecret(): string {
  const secret = process.env.JWT_SECRET;
  if (!secret) {
    throw new Error('JWT_SECRET environment variable is required — see .env.example');
  }
  return secret;
}

// ─────────────────── Password Hashing ───────────────────

export function hashPassword(password: string): string {
  return bcrypt.hashSync(password, 10);
}

export function verifyPassword(plain: string, hashed: string): boolean {
  return bcrypt.compareSync(plain, hashed);
}

// ─────────────────── JWT Tokens ───────────────────

export function createToken(userId: string, email: string): string {
  return jwt.sign({ sub: userId, email }, getJwtSecret(), { expiresIn: TOKEN_EXPIRE });
}

export function verifyToken(token: string): { sub: string; email: string } | null {
  const secret = getJwtSecret(); // throws loudly if unset, instead of failing all logins silently
  try {
    return jwt.verify(token, secret) as { sub: string; email: string };
  } catch {
    return null;
  }
}

// ─────────────────── Request Helpers ───────────────────

/**
 * Extract and verify user from the Authorization header.
 * Returns the full User record or null if unauthenticated.
 */
export async function getUserFromRequest(request: NextRequest) {
  const authHeader = request.headers.get('Authorization');
  if (!authHeader?.startsWith('Bearer ')) return null;

  const token = authHeader.slice(7);
  const payload = verifyToken(token);
  if (!payload) return null;

  const user = await prisma.user.findUnique({ where: { id: payload.sub } });
  return user;
}
