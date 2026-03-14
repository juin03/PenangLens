import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { NextRequest } from 'next/server';
import { prisma } from './prisma';

const JWT_SECRET = process.env.JWT_SECRET || 'penanglens-dev-secret';
const TOKEN_EXPIRE = '24h';

// ─────────────────── Password Hashing ───────────────────

export function hashPassword(password: string): string {
  return bcrypt.hashSync(password, 10);
}

export function verifyPassword(plain: string, hashed: string): boolean {
  return bcrypt.compareSync(plain, hashed);
}

// ─────────────────── JWT Tokens ───────────────────

export function createToken(userId: string, email: string): string {
  return jwt.sign({ sub: userId, email }, JWT_SECRET, { expiresIn: TOKEN_EXPIRE });
}

export function verifyToken(token: string): { sub: string; email: string } | null {
  try {
    return jwt.verify(token, JWT_SECRET) as { sub: string; email: string };
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
