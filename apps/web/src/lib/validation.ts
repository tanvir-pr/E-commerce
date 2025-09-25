import { z } from "zod";

export function registerSchema(messages: { email: string; password: string; confirm: string }) {
  return z
    .object({
      email: z.string().trim().email(messages.email),
      password: z.string().min(10, messages.password),
      confirmPassword: z.string(),
    })
    .refine((value) => value.password === value.confirmPassword, {
      message: messages.confirm,
      path: ["confirmPassword"],
    });
}

export function loginSchema(messages: { email: string; password: string }) {
  return z.object({
    email: z.string().trim().email(messages.email),
    password: z.string().min(1, messages.password),
  });
}

export function passwordPairSchema(messages: { password: string; confirm: string }) {
  return z
    .object({
      password: z.string().min(10, messages.password),
      confirmPassword: z.string(),
    })
    .refine((value) => value.password === value.confirmPassword, {
      message: messages.confirm,
      path: ["confirmPassword"],
    });
}

export function phoneRegisterSchema(messages: {
  name: string;
  phone: string;
  password: string;
  confirm: string;
}) {
  return z
    .object({
      name: z.string().trim().min(1, messages.name).max(200),
      phone: z.string().trim().regex(/^\+[1-9]\d{7,14}$/, messages.phone),
      password: z.string().min(10, messages.password),
      confirmPassword: z.string(),
    })
    .refine((value) => value.password === value.confirmPassword, {
      message: messages.confirm,
      path: ["confirmPassword"],
    });
}

export function codeSchema(message: string) {
  return z.object({
    code: z.string().trim().min(6, message).max(32),
  });
}
