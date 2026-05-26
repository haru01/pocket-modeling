import { z } from "zod";

export const IdSchema = z.object({
  uuid: z.string().uuid(),
  slug: z
    .string()
    .min(1)
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
});

export const ConfidenceSchema = z.enum(["known", "assumed", "open"]);

export const ActorSchema = z.object({
  id: IdSchema,
  name: z.string().min(1),
  type: z.enum(["human", "system", "external"]),
  notes: z.string().optional(),
});

export const PolicySchema = z.object({
  id: IdSchema,
  name: z.string().min(1),
  description: z.string().min(1),
  trigger: z.string().min(1),
  confidence: ConfidenceSchema.default("known"),
  questions: z.array(z.string()).default([]),
});

export const CommandSchema = z.object({
  id: IdSchema,
  name: z.string().min(1),
  actorSlug: z.string().min(1),
  intent: z.string().min(1),
  preconditions: z.array(z.string()).default([]),
  policySlugs: z.array(z.string()).default([]),
  confidence: ConfidenceSchema.default("known"),
  questions: z.array(z.string()).default([]),
});

export const EventSchema = z.object({
  id: IdSchema,
  name: z.string().min(1),
  sequence: z.number().int().nonnegative(),
  occurredAtHint: z.string().optional(),
  triggerActorSlug: z.string().optional(),
  commandSlugs: z.array(z.string()).default([]),
  policySlugs: z.array(z.string()).default([]),
  contextSlug: z.string().optional(),
  aggregateSlug: z.string().optional(),
  confidence: ConfidenceSchema.default("known"),
  questions: z.array(z.string()).default([]),
});

export const BoundedContextSchema = z.object({
  id: IdSchema,
  name: z.string().min(1),
  boundaryReason: z.string().min(1),
  ownedEventSlugs: z.array(z.string()).default([]),
  ownedCommandSlugs: z.array(z.string()).default([]),
  questions: z.array(z.string()).default([]),
});

export const AggregateSchema = z.object({
  id: IdSchema,
  name: z.string().min(1),
  contextSlug: z.string().min(1),
  invariantHypotheses: z.array(z.string()).default([]),
  relatedEventSlugs: z.array(z.string()).default([]),
  relatedCommandSlugs: z.array(z.string()).default([]),
  questions: z.array(z.string()).default([]),
});

export const QuestionSchema = z.object({
  id: IdSchema,
  text: z.string().min(1),
  relatedType: z.enum([
    "event",
    "command",
    "policy",
    "actor",
    "context",
    "aggregate",
    "general",
  ]),
  relatedSlug: z.string().optional(),
  status: z.enum(["open", "resolved"]).default("open"),
  owner: z.string().optional(),
});

export const WorkshopModelSchema = z.object({
  workshopMeta: z.object({
    title: z.string().min(1),
    domain: z.string().min(1),
    date: z.string().min(1),
    durationMinutes: z.number().int().positive().default(90),
  }),
  actors: z.array(ActorSchema).default([]),
  policies: z.array(PolicySchema).default([]),
  commands: z.array(CommandSchema).default([]),
  events: z.array(EventSchema).default([]),
  contexts: z.array(BoundedContextSchema).default([]),
  aggregates: z.array(AggregateSchema).default([]),
  questions: z.array(QuestionSchema).default([]),
});

export type WorkshopModel = z.infer<typeof WorkshopModelSchema>;
