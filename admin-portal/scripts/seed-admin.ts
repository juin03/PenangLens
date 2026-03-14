/**
 * Admin seeder — run this once to promote a user to admin
 * Usage: npx ts-node scripts/seed-admin.ts your@email.com
 */
import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

async function main() {
  const email = process.argv[2];
  const password = process.argv[3];

  if (!email) {
    console.error('Usage: npx ts-node scripts/seed-admin.ts <email> [password]');
    process.exit(1);
  }

  // Find existing user
  let user = await prisma.user.findFirst({ where: { email } });

  if (user) {
    // Promote existing user to admin
    user = await prisma.user.update({ where: { id: user.id }, data: { role: 'admin' } });
    console.log(`✅ Promoted ${email} to admin!`);
  } else if (password) {
    // Create new admin user
    const hashed = await bcrypt.hash(password, 12);
    user = await prisma.user.create({
      data: { email, hashedPassword: hashed, role: 'admin', name: 'Admin' },
    });
    console.log(`✅ Created admin user: ${email}`);
  } else {
    console.error(`User ${email} not found. To create a new admin: npx ts-node scripts/seed-admin.ts <email> <password>`);
    process.exit(1);
  }

  console.log(`   Role: ${user.role}`);
  console.log(`   ID:   ${user.id}`);
}

main().catch(console.error).finally(() => prisma.$disconnect());
