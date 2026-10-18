"use client";

import {
  AIInput,
  type AIInputMenuItem,
  type PromptSettingGroup,
} from "@/components/ui/ai-input";
import { Archive, Camera, LayoutGrid, Paperclip, Plug } from "lucide-react";

const settingGroups: PromptSettingGroup[] = [
  {
    id: "model",
    label: "Model",
    display: "featured",
    options: [
      { value: "gemma-ai", label: "Gemma AI", description: "Most capable analytical model" },
      { value: "gemma-ai-fast", label: "Gemma AI Fast", description: "Faster responses" },
    ],
  },
  {
    id: "effort",
    label: "Effort",
    display: "submenu",
    options: [
      { value: "high", label: "High" },
      { value: "medium", label: "Medium" },
      { value: "low", label: "Low" },
    ],
  },
];

const menuItems: AIInputMenuItem[] = [
  {
    value: "select-dataset",
    label: "Select Dataset",
    icon: Paperclip,
    shortcut: "⌘D",
  },
  { value: "explore-data", label: "Explore Data", icon: Camera },
  {
    value: "suggested-questions",
    label: "Suggested Questions",
    icon: Archive,
    items: [
      { value: "top-energy-consumers", label: "Top Energy Consumers 2024" },
      { value: "quarterly-revenue-trend", label: "Quarterly Revenue Trend" },
    ],
  },
  { value: "sep-1", type: "separator" },
  {
    value: "skills",
    label: "Skills & Connectors",
    icon: LayoutGrid,
    items: [
      { value: "snowflake-sql", label: "Snowflake SQL Engine" },
      { value: "data-dictionary", label: "Data Dictionary" },
    ],
  },
  { value: "add-connector", label: "Add connector", icon: Plug },
];

export default function AIInputPreview() {
  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-10">
      <AIInput
        menuItems={menuItems}
        settingGroups={settingGroups}
        onMenuSelect={(value) => console.log("menu:", value)}
        onSettingsChange={(settings) => console.log("settings:", settings)}
        onSend={(message, meta) => console.log(message, meta)}
        placeholder="Ask anything about your data in plain language..."
      />
    </div>
  );
}
