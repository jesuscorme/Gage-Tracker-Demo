"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppShell } from "@/components/shell";
import { Loading } from "@/components/ui";
import { useAuth } from "@/lib/auth";

export default function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  const { ready, me } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (ready && !me) router.replace("/login");
  }, [ready, me, router]);

  if (!ready || !me) {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Loading />
      </div>
    );
  }
  return <AppShell>{children}</AppShell>;
}
